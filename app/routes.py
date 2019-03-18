import os
import pandas as pd
from flask import render_template, flash, redirect, url_for, request, session
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy.sql import or_, asc
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
from app import app, bcrypt, logger
from app.ThreadingManager import ThreadingManager, EmailManager
from app.forms import RedditAccountConfiguration, AutoMessengerSettings, RegistrationForm, LoginForm, PostForm
from app.models import db, Users, FlaggedComments, Messages
from app.scripts.main import build_keywords, open_subject, open_message
from app.scripts.reddit_tools import reddit
from app.models import Company, PrimaryKeywords,  SecondaryKeywords, primary_key_subscribers, \
    flagged_comments_primary_key_mapping

# GLOBALS + ADDITIONAL PARAMS
pd.set_option('display.max_colwidth', 200)
db.create_all()
db.session.commit()

manager = ThreadingManager()
ALLOWED_EXTENSIONS = ['csv']

# TEST CODE:
# from app.scripts.reddit_reader import RedditReader
from app.scripts.email_reader import EmailReader
e_reader = EmailReader(reddit)
e_reader.run()
# reader = RedditReader(reddit)
# reader.reply_checker()


@app.before_first_request
def init_app():
    """
    LOAD ALL NECESSARY SESSION VARIABLES HERE
    :return:
    """
    session['message_content'] = open_message()
    session['subject_content'] = open_subject()
    logger.info('LOADED MESSAGE CONTENT')
    # email_manager = EmailManager()
    # email_manager.start_wan_writer()
    # email_manager.start_email_engine()
    # logger.info('EMAIL MANAGER STARTED')


@app.route("/about")
def about():
    """
    ROUTE FOR THE ABOUT PAGE

    :return:
    """
    # TODO: move out of here
    reddit.message_user("Eggplay", "test sub", "test")

    return render_template("about.html")


@app.route("/", methods=["POST", "GET"])
@app.route("/reddit_scraper", methods=["POST", "GET"])
@login_required
def reddit_scraper():
    """
    ROUTE FOR LANDING PAGE. THIS PAGE DISPLAYS A TABLE OF ALL FLAGGED COMMENTS THAT ARE STORED IN THE DB & UNPROCESSED,
    ALSO LINKS THOSE RECORDS TO A COMMENT OVERVIEW PAGE


    :return:
    """
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    try:
        company_pks = Company.query.join(primary_key_subscribers).filter(
            primary_key_subscribers.c.company== current_user.company_name).first().primary_keywords
        flagged_comment_ids = set(i for i in FlaggedComments.query.join(
            flagged_comments_primary_key_mapping).join(PrimaryKeywords).filter(
            flagged_comments_primary_key_mapping.c.primary_key.in_(
                [i.id for i in company_pks])).with_entities(FlaggedComments.id).all())

        # ONLY GET COMMENTS THAT HAVEN'T BEEN MESSAGED
        query = FlaggedComments.query.filter(FlaggedComments.id.in_(flagged_comment_ids)).filter(
            FlaggedComments.was_user_contacted.is_(False)).options(
            db.defer('comment_id'),
            db.defer('was_comment_deleted'),
            db.defer('was_user_contacted'),
            db.defer('polarity'),
            db.defer('subjectivity'))
        pending_records_size = query.count()
    except AttributeError:
        pending_records_size = 0

    if pending_records_size:
        current_records = FlaggedComments.records_to_dataframe(query)
        current_records['more_info'] = current_records['id'].apply(
            lambda x: "<a href=" + url_for('comment_overview', pid=x) + ">More Info</a>")
        current_records['reddit_link'] = current_records['reddit_link'].apply(lambda x:
                                                                              '<a href="https://{}" target="blank"> '
                                                                              'Click Here </a>'.format(x))
        current_records['user_comment'] = current_records['user_comment'].str.replace('\n', '<br>')
        current_records = FlaggedComments.format_df_columns(current_records, "Comment ID", 'Subjectivity', 'Polarity')
        table_headers = current_records.columns.tolist()
    else:
        table_headers = []
        current_records = pd.DataFrame()

    auto_messenger_form = AutoMessengerSettings()

    if auto_messenger_form.validate_on_submit():
        manager.start_auto_messenger(reddit, auto_messenger_form.number_of_messages.data, auto_messenger_form.sleep_time.data,
                                     session['message_content'], session['subject_content'], current_user.company_email)

    return render_template("reddit_scraper.html",
                           title="Flagged Comments - {size} Unresolved".format(size=pending_records_size),
                           records=current_records,
                           table_headers=table_headers,
                           rs_pid=manager.running(),
                           auto_messenger_form=auto_messenger_form
                           )


# this route is called when entering the detail view AND
# when a comment is submitted from within the detail view
@app.route("/comment_overview/<pid>", methods=['GET', 'POST'])
@login_required
def comment_overview(pid):
    """
    ROUTE FOR DISPLAYING THE COMMENT OVERVIEW PAGE

    :param pid:
    :return:
    """

    # GRAB SPECIFIC USER RECORDS VIA THE PRIMARY KEY ID (PID)
    current_records = FlaggedComments.query.filter_by(id=int(pid)).options(db.defer('was_comment_deleted'),
                                                                           db.defer('was_user_contacted'))
    current_records_unpacked = current_records.all()

    # IF THE DATA-FRAME IS EMPTY, RETURN A BLANK TEMPLATE
    if not current_records.first():
        return render_template('reddit_scraper.html')

    # TODO: Make intent of below question clear
    # What does it mean if there is more than a single current record?
    current_record = current_records_unpacked[0]

    # GRAB SPECIFIC USER RECORDS VIA THE PRIMARY KEY
    current_record = FlaggedComments.query.filter_by(id=int(pid))
    try:
        username = current_record.first().username
        current_record = current_record.first()
    except IndexError as e:
        flash("Record No Longer Exists!", 'warning')
        return redirect('reddit_scraper')

    # CHECK IF USER IS IN PROCESSED COMMENTS DB
    if FlaggedComments.was_user_messaged(username):
        # USE FOR TESTING
        # TODO: come back here
        flash("THIS USER HAS BEEN CONTACTED", 'warning')
        conversation = Messages.query.order_by(
            asc(Messages.date_sent)).filter(
            or_(Messages.sender.like(current_record.username), Messages.recipient.like(current_record.username))).all()
        replies = conversation
    else:
        flash("THIS USER HAS NOT BEEN CONTACTED", "info")
        replies = []

    # READ THE SQL INTO A PANDAS DATA-FRAME
    current_record_df = FlaggedComments.records_to_dataframe(current_records)

    # CREATE COLUMN FOR REDDIT LINK
    current_record_df['reddit_link'] = current_record_df['reddit_link'].apply(
        lambda x: '<a href="https://{}" target="blank"> Click Here </a>'.format(x))

    current_record_df = FlaggedComments.format_df_columns(current_record_df, "See Details")

    # TODO: REMOVE FOR PRODUCTION

    subreddit = str(current_record_df['r/'][0])
    user_comment = current_record_df['Comment'][0]

    if request.method == 'POST':
        if request.form.get('message', None) == 'Send Message':
            message = request.form['body']
            subject = request.form['subject']
            recipient = request.form['recipient']
            # TODO FIX
            success = reddit.message_user(recipient, subject, message, current_user.company_email)

            if success:
                logger.info('MESSAGE SENT TO USER {recipient}'.format(recipient=username.upper()))
                current_record.was_user_contacted = 1
                db.session.commit()
            else:
                session.pop('_flashes', None)
                flash('FAILED TO SEND MESSAGE. CHECK REDDIT ACCOUNT STATUS!', 'warning')
                return redirect(url_for("reddit_scraper"))
        else:
            # adding a record to remove automatically deletes it from Flagged
            current_record.was_comment_removed = 1

        session.pop('_flashes', None)
        return redirect(url_for('reddit_scraper'))

    del current_record_df['ID']
    del current_record_df['Comment']
    del current_record_df['Comment ID']

    table_headers = current_record_df.columns.tolist()
    form = PostForm()
    # READ MESSAGE INFORMATION

    # FORMAT PRE POPULATED MESSAGE WITH USERNAME AND SUBREDDIT

    form.body.data = session['message_content'].format(username=username, subreddit=subreddit,
                                                       user_comment=current_record.user_comment)
    form.subject.data = session['subject_content']
    form.recipient.data = username
    return render_template("comment_overview.html",
                           title="Comment Overview For User: <b>{username}</b>".format(username=username),
                           table_headers=table_headers,
                           records=current_record_df,
                           form=form,
                           user_comment=user_comment,
                           replies=replies)


@app.route('/start_reddit_scraper')
@login_required
def start_reddit_scraper():
    """
    ROUTE THAT SPAWNS OFF A SEPARATE PROCESS FOR THE SCRAPER THAT PULLS COMMENTS

    :return:
    """

    # if not q.count:
    #     r_scraper = q.enqueue(reddit.run_reddit_scraper, result_ttl=-1)
    #     r_flagger = q.enqueue(parse_reddit_comments, result_ttl=-1)
    #
    # else:
    #
    if manager.start_thread_if_not_running():
        flash("We're already looking for Complainers. Sometimes they're hard to catch! You will be notified as soon as they are.",
            "success")
    return redirect(url_for('reddit_scraper'))


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect('/')
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        user = Users(full_name=form.full_name.data,
                     company_email=form.company_email.data,
                     company_phone=form.company_phone.data,
                     username=form.username.data,
                     password=hashed_password)

        db.session.add(user)
        company_name = form.company_name.data.lower().strip()
        company_exists = Company.query.filter(Company.company_name == company_name).first()
        if company_exists:
            company_exists.users.append(user)
        else:
            company = Company(company_name=company_name, users=[user])
            db.session.add(company)
        db.session.commit()
        session.clear()
        login_user(user, remember=form.remember.data)
        flash("Account created for {}".format(form.username.data), 'success')
        # next_page = request.args.get('next')
        # redirect(next_page) if next_page else
        return redirect(url_for('reddit_scraper'))
    return render_template("new_registration.html", title="Register", form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    """
    ROUTE FOR LOGGING IN

    :return:
    """

    if current_user.is_authenticated:
        return redirect(url_for('reddit_scraper'))
    form = LoginForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            # session['number'] = consequent_integers.next()
            login_user(user, remember=form.remember.data)

            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('reddit_scraper'))
        else:
            flash('Login Unsuccessful.', 'danger')

    return render_template("login.html", title="Login", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect('/')


@app.route("/account")
@login_required
def account():
    """
    ROUTE FOR VIEW ACCOUNT

    :return:
    """

    return render_template('account.html', title='Account')


@app.route('/company_portal', methods=['POST', 'GET'])
@login_required
def company_portal():

    post_form = PostForm()
    form = RedditAccountConfiguration()

    if post_form.validate_on_submit():
        # UPDATE GLOBALS
        session['message_content'] = post_form.body.data
        session['subject_content'] = post_form.subject.data

    if form.validate_on_submit():
        reddit.refresh_token(form.client_id.data, form.client_secret.data,
                             form.reddit_password.data, 'test_script', form.reddit_account_username.data)

        reddit.build_connection()

    associations = Company.query.join(primary_key_subscribers).filter(
        primary_key_subscribers.c.company == current_user.company_name).first()

    if associations:
        primary_keywords = associations.primary_keywords
        secondary_keywords = associations.secondary_keywords
        return render_template('company_portal.html',
                               primary_keywords=primary_keywords,
                               secondary_keywords=secondary_keywords,
                               form=form,
                               reddit=reddit,
                               post_form=post_form,
                               message_content=session['message_content'],
                               subject_content=session['subject_content'])

    return render_template("company_portal.html",
                           form=form,
                           reddit=reddit,
                           post_form=post_form,
                           message_content=session['message_content'],
                           subject_content=session['subject_content'])


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/uploader', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        try:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                if not os.path.isdir(app.config["UPLOAD_FOLDER"]):
                    os.makedirs(app.config["UPLOAD_FOLDER"])
                file.save(file_path)
                flash('File Uploaded Successfully', 'success')
                data = read_uploaded_file(file_path)
                add_keywords_to_db(data)
                delete_unused_primary_keys()
        except HTTPException:
            flash('Failed Upload. Are you sure you selected the correct file?', 'warning')
            redirect('company_portal')
    return redirect('company_portal')





"""
\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
ONLY PUT HELPER FUNCTIONS BELOW. PUT ADDITIONAL ROUTES ABOVE
\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
"""


def read_uploaded_file(file_path):
    keywords = build_keywords(file_path)
    os.remove(file_path)
    return keywords


def add_keywords_to_db_helper(data):
    # GET COMPANY
    company = Company.query.filter(Company.id==current_user.company_name).first()
    # GET EXISTING PRIMARY KEYS FROM DB
    db_primary_keywords = db.session.query(PrimaryKeywords).all()
    # GET EXISTING SECONDARY KEYS
    db_secondary_keywords = db.session.query(SecondaryKeywords).all()
    # CONVERT TO SET(SO WE CAN DO SET OPERATIONS)
    new_primary_keys = set(data['primary'])
    new_secondary_keys = set(data['secondary'])
    existing_primary_keywords = set([pk.primary_keyword for pk in db_primary_keywords])
    existing_secondary_keywords = set([sk.secondary_keyword for sk in db_secondary_keywords])
    # FIND THE UNIQUE PRIMARY KS AND SECONDARY KEYS TO ADD TO THE DB
    unique_pks = new_primary_keys - existing_primary_keywords
    unique_sks = new_secondary_keys - existing_secondary_keywords
    # add all unique keywords to list and subscribe to them. must be separate in case one list has is empty
    for prim in unique_pks:
        primary = PrimaryKeywords(primary_keyword=prim)
        db.session.add(primary)
        db.session.commit()
        primary.primary_key_subs.append(company)
        db.session.commit()
    for sec in unique_sks:
        secondary = SecondaryKeywords(secondary_keyword=sec)
        db.session.add(secondary)
        db.session.commit()
        secondary.secondary_key_subs.append(company)
        db.session.commit()
    # get all existing keywords that user wants to subscribe to and add to company sub list
    for pk, sk in zip(db_primary_keywords, db_secondary_keywords):
        if pk.primary_keyword in new_primary_keys:
            pk.primary_key_subs.append(company)
        if sk.secondary_keyword in new_secondary_keys:
            sk.secondary_key_subs.append(company)
        db.session.commit()


def add_keywords_to_db(data):
    # TODO: IMPLEMENT AUTOMATIC DELETION OF UNUSED KEYWORDS, BOTH PRIMARY AND SECONDARY
    associations = Company.query.join(primary_key_subscribers).filter(
        primary_key_subscribers.c.company == current_user.company_name).first()
    if associations:
        # IF USER ALREADY HAS ASSOCIATIONS, DELETE THEM. FILE UPLOAD REPLACES ALL SUBSCRIPTIONS
        associations.primary_keywords = []
        associations.secondary_keywords = []
        db.session.commit()
    add_keywords_to_db_helper(data)


def delete_unused_primary_keys():
    # GET ALL PRIMARY KEYS
    pk_universe = [pk.id for pk in PrimaryKeywords.query.all()]
    # GET ALL PRIMARY KEYS THAT ARE CURRENTLY SUBSCRIBED TO
    pks_with_subscriptions = [pk.id for pk in PrimaryKeywords.query.join(primary_key_subscribers).all()]
    # REMOVE PRIMARY KEYS FROM UNIVERSE LIST THAT ARE CURRENTY SUBSCRIBED TO
    deletes = [i for i in pk_universe if i not in pks_with_subscriptions]
    # DELETE UNUSED KEYWORDS TO REDUCE COMMENTS BEING FLAGGED
    PrimaryKeywords.query.filter(PrimaryKeywords.id.in_(deletes)).delete(synchronize_session='fetch')
    # COMMIT CHANGES
    db.session.commit()