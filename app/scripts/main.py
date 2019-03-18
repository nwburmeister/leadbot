__author__ = 'Nik Burmeister'
import csv
import datetime
import time
import os
import langdetect
from app.models import ScrapedComments, PrimaryKeywords, SecondaryKeywords, Messages, db
from app.models import FlaggedComments, db
from app import logger
from textblob import TextBlob
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import FlushError
from langdetect.lang_detect_exception import LangDetectException


def open_message():
    """
    HELPER FUNCTION TO OPEN PRE-WRITTEN MESSAGE
    :return:
    """
    message_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data/message.txt'))
    message_file = open(message_path, "r")
    message_content = message_file.readlines()
    message = ""
    for mess in message_content:
        message += mess

    return message


def open_subject():
    """
    HELPER FUNCTION TO OPEN PRE-WRITTEN SUBJECT
    :return:
    """
    subject_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data/subject.txt'))
    subject_file = open(subject_path, "r")
    subject_text = subject_file.readlines()
    return subject_text[0]


def batch_reddit_messenger(record, reddit, subject_content, message_content, ca_auto_message_user):
    # TODO: IMPLEMENT DYNAMIC MESSAGE EDITING: WE WANT TO BE ABLE TO PASS ANY LIST OF ARGS AND INSERT THEM INTO A MESSAGE
    """

    :param record:
    :param reddit:
    :param subject_content:
    :param message_content:
    :param ca_auto_message_user:
    :return:
    """
    username = 'bluerhino1545'
    subreddit = record.subreddit
    message = message_content.format(subreddit=subreddit,
                           user_comment=" ".join(i for i in record.user_comment.split()[0:25]) + "...",
                           username=username)
    reddit.message_user(username, subject_content, message, ca_auto_message_user)
    logger.info('MESSAGE SENT TO USER {recipient}'.format(recipient=username.upper()))
    FlaggedComments.query.filter(FlaggedComments.username == username).was_user_messaged = 1
    db.session.commit()


def auto_message(reddit, num_messages, wait_time, message_content, subject_content):
    """
    FUNCTION FOR AUTO MESSAGING PEOPLE

    :param reddit:
    :param num_messages:
    :param wait_time:
    :param message_content:
    :param subject_content:
    :return:
    """
    counter = 0
    while counter < num_messages:
        current_records = FlaggedComments.query.filter().all()
        for record in current_records:
            # todo: implement time check
            username = record.username
            if (not 'moderator' in username.lower()) & (not 'bot' in username.lower()):
                # TODO: FIX PROCESSED COMMENTS
                if FlaggedComments.was_user_messaged(username):
                    batch_reddit_messenger(record, reddit, subject_content, message_content)
                    record.was_user_contacted = 1
                    counter += 1
                    time.sleep(wait_time)
            else:
                # IF PRESENT IN USERNAME, WE WANT TO DROP RECORD FROM TABLE
                db.session.delete(record)

            db.session.commit()
        break





def datetime_from_utc_to_local(utc_time):
    """
    Function to convert UTC to local time
    Depends on timezone
    :param utc_time:
    :return:
    """
    # TODO: THIS IS AN ATROCIOUS SOLUTION
    return datetime.datetime.strptime(time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(float(utc_time))),
                                      "%Y/%m/%d %H:%M:%S")


def build_keywords(path=None):
    """
    Function for importing a CSV file of keywords.
    :return:
    """
    # TODO: PREVENT EMPTY STRINGS FROM ENTERING LISTS
    master_list = []
    split_list = {'primary': [], 'secondary': []}
    if not path:
        path = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'data/kwarg_list.csv'))
    with open(path, newline='') as csvfile:
        kwarg_list = csv.reader(csvfile, delimiter=',')
        master_list.append([row for row in kwarg_list])
        for row in master_list[0][1:]:
            split_list['primary'].append(row[0].lower())
            split_list['secondary'].append(row[1].lower())

    return split_list


def build_subreddit_universe():
    """
    Function for importing a list of all subreddits
    :return:
    """
    master_list = []

    with open("subreddits.csv", newline='') as csvfile:
        subreddits = csv.reader(csvfile, delimiter=',')
        master_list.append([row for row in subreddits])

    return master_list


def contains_word(s, w):
    """
    Helper function for searching a reddit comment string and matching keywords
    :param s:
    :param w:
    :return:
    """
    return (' ' + w + ' ') in (' ' + s + ' ')


def detect_language(comment):
    """
    FUNCTION FOR UNDERSTANDING THE
    :param comment:
    :return:
    """
    try:
        lang = langdetect.detect(comment)
    except LangDetectException:
        return 'en'
    return lang


def inspect_comment(comment, primary_keywords, secondary_keywords):
    """
    # TODO: FIND BETTER SOLUTION
    Function to search comment for keywords
    :return:
    """

    pks_found = []
    sks_found = []

    # TODO: UPDATE...THIS IS FUCKING ARBITRARY
    if (len(comment.split()) > 12) and (detect_language(comment.lower()) != 'en'):
        return pks_found, sks_found

    #  1. SEARCH FOR PRIMARY KEYWORDS IN COMMENT

    for primary_key in primary_keywords:
        if contains_word(comment, primary_key.primary_keyword):
            # create relationship in db
            pks_found.append(primary_key)
            # search for secondary keywords
            for secondary_key in secondary_keywords:
                if contains_word(comment, secondary_key.secondary_keyword):
                    sks_found.append(secondary_key)

    return pks_found, sks_found


def build_comment(comment):
    """
    Helper function for building flagged comment info
    :param comment:
    :param keywords_found:
    :param flagged_comments:
    :return:
    """
    comment_as_dict = comment.__dict__
    comment_as_dict.pop('_sa_instance_state', None)
    comment_analysis = TextBlob(comment_as_dict['user_comment'].lower())
    comment_as_dict['subreddit'] = str(comment.subreddit)
    comment_as_dict['polarity'] = round(comment_analysis.sentiment.polarity, 4)
    comment_as_dict['subjectivity'] = round(comment_analysis.sentiment.subjectivity, 4)
    comment_as_dict['comment_date'] = comment_as_dict['comment_date']
    comment_as_dict['reddit_link'] = comment.reddit_link
    comment_as_dict['detected_language'] = detect_language(comment_as_dict['user_comment'].lower())
    comment_as_dict['was_user_contacted'] = 0
    comment_as_dict['was_comment_deleted'] = 0
    return FlaggedComments(**comment_as_dict)


def add_flagged_comment_to_db(flagged_comment, primary_keywords, secondary_keywords):
    """
    FUNCTION FOR ADDING A FLAGGED COMMENT WITH ITS RESPECTIVE PKS AND SKS
    TO THE DB
    :param comment_list:
    :return:
    """

    try:
        db.session.add(flagged_comment)
        db.session.commit()
        [i.fc_pk_mapping.append(flagged_comment) for i in primary_keywords]
        # MAKE SURE LIST IS POPULATE. PRIMARY_KEYWORDS CHECK IS DONE IN CALLER
        if secondary_keywords:
            [i.fc_sk_mapping.append(flagged_comment) for i in secondary_keywords]
        db.session.commit()
        logger.info("--FLAGGED COMMENTS ADDED TO DB--")
    except (IntegrityError, FlushError):
        db.session.rollback()
        if len(FlaggedComments.query.filter_by(username=flagged_comment.username).all()) > 0:
            logger.info("COMMENT ALREADY PRESENT FOR UN: {username}".format(username=flagged_comment.username))
        else:
            logger.critical("{} COULD NOT ADD TO DB".format(flagged_comment.reddit_link))


def parse_reddit_comments():
    logger.info("PARSING REDDIT COMMENTS")
    while True:
        # GET ALL REDDIT COMMENTS
        comments = db.session.query(ScrapedComments).all()
        if comments:
            drop_ids = [comment.comment_id for comment in comments]
            # WE DONT DROP THE ENTIRE TABLE BECAUSE OUR SCRIPT IS (POSSIBLY) WRITING CONCURRENTLY
            db.session.query(ScrapedComments).filter(ScrapedComments.comment_id.in_(drop_ids)).delete(synchronize_session='fetch')
            db.session.commit()
            # NEED TO MAKE DB CALL EVERY TIME IN-CASE NEW KEYWORDS ARE UPLOADED
            # TODO: COULD WE HAVE AN ASYCN REQUEST GIVE A WARNING THAT KEYWORDS HAVE BEEN UPDATED?
            primary_keywords_list = PrimaryKeywords.query.all()
            secondary_keywords_list = SecondaryKeywords.query.all()
            for comment in comments:
                if not ('moderator' in comment.username or 'bot' in comment.username):
                    primary_keywords, secondary_keywords = inspect_comment(comment.user_comment.lower(),
                                                                           primary_keywords_list,
                                                                           secondary_keywords_list)
                    if primary_keywords:
                        flagged_comment = build_comment(comment)
                        add_flagged_comment_to_db(flagged_comment, primary_keywords, secondary_keywords)


if __name__ == "__main__":
    parse_reddit_comments()