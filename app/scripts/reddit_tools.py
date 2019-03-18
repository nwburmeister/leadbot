import praw
import time
import traceback
import datetime
from app import logger
from app.models import ScrapedComments
from app.models import db, Messages
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import FlushError


class RedditHelper(object):

    def __init__(self, client_id, client_secret, password, user_agent, username):
        self.client_id = client_id
        self.client_secret = client_secret
        self.password = password
        self.user_agent = user_agent
        self.username = username
        self.pid = None
        self.comments = []
        self.reddit_conn = None

    def refresh_token(self, client_id, client_secret, password, user_agent, username):
        reddit = praw.Reddit(client_id=client_id,
                             client_secret=client_secret,
                             password=password,
                             username=username,
                             redirect_uri='http://localhost:8080',
                             user_agent='praw_refresh_token_example')
        self.client_id = client_id
        self.client_secret = client_secret
        self.password = password
        self.user_agent = user_agent
        self.username = username
        self.reddit_conn = reddit

    def build_connection(self):
        reddit = praw.Reddit(client_id=self.client_id,
                             client_secret=self.client_secret,
                             password=self.password,
                             user_agent=self.user_agent,
                             username=self.username)
        self.reddit_conn = reddit

    @staticmethod
    def build_comment(comment):
        db_comment = ScrapedComments(comment_id=comment.id,
                                     username=str(comment.author),
                                     date_found=datetime.datetime.now(),
                                     user_comment=str(comment.body.lower()),
                                     comment_date=datetime_from_utc_to_local(comment.created_utc),
                                     reddit_link=str('reddit.com' + comment.permalink),
                                     subreddit=str(comment.subreddit_name_prefixed),
                                     submission_title=str(comment.link_title),
                                     )
        return db_comment

    def add_reddit_comments_to_db(self):
        # TODO: WE'RE DROPPING COMMENTS DUE TO HOW WE'RE PUSHING DUPLICATE COMMENTS TO THE DB. HIGH PRIORITY FIX AFTER
        # TODO: V1 is released
        try:
            db.session.bulk_save_objects(self.comments)
            db.session.commit()
            logger.info("COMMENT PULL ADDED TO DB")
        except IntegrityError:
            db.session.rollback()
            # logger.warning("INTEGRITY ERROR. ROLLING BACK AND RETRYING.")
            while self.comments:
                comment = self.comments.pop()
                try:
                    db.session.add(comment)
                    db.session.flush()
                except (IntegrityError, FlushError):
                    db.session.rollback()
                db.session.commit()
            logger.info("COMMENTS ADDED TO DB WITH ERRORS")

    def message_user(self, reddit_user, subject, message, sender_email):
        # TODO: CREATE MODULE TO ENCAPSULATE REDDIT FUNCTIONALITY
        """
        SEND A REDDIT USER A MESSAGE

        :param reddit: REDDIT INSTANCE
        :param reddit_user: USERS NAME (STR)
        :param subject: MESSAGE SUBJECT (STR)
        :param message: MESSAGE TO SEND (STR)
        :return:
        """
        try:
            self.reddit_conn.redditor(reddit_user).message(subject, message)
        except Exception:
            logger.critical('----------Error encountered----------')
            tb = traceback.format_exc()
            logger.critical(tb)
            logger.critical('-------------------------------------')
            return False
        message = Messages(sender=sender_email,
                           recipient=reddit_user,
                           body=message,
                           subject=subject,
                           date_sent=datetime.datetime.now(),
                           has_been_sent_for_processing=0,
                           ca_user_id_assoc='parent')
        Messages.add_record(message)
        db.session.commit()
        return True

    def run_reddit_scraper(self):
        logger.info("REQUESTING COMMENT STREAM")

        while True:
            # logger.info(threading.current_thread())
            try:
                comments = self.reddit_conn.subreddit('all').stream.comments(pause_after=-1)
                for comment in comments:
                    self.comments.append(self.build_comment(comment))
            except (Exception, AttributeError) as e:
                if isinstance(type(e), AttributeError.__class__):
                    self.add_reddit_comments_to_db()
                    self.comments = []
                else:
                    logger.critical('----------Error encountered----------')
                    tb = traceback.format_exc()
                    logger.critical(tb)
                    logger.critical('-------------------------------------')


def add_to_db(comment_list):
    """
    FUNCTION FOR ADDING A COMMENT TO THE DB
    :param comment_list:
    :return:
    """

    while comment_list:
        comment = comment_list.pop()
        try:
            db.session.add(comment)
            db.session.commit()
            logger.info("FLAGGED COMMENTS ADDED TO DB")
        except (IntegrityError, FlushError):
            print("{} could not be added to db".format(comment))
            db.session.rollback()


def datetime_from_utc_to_local(utc_time):
    """
    Function to convert UTC to local time
    Depends on timezone
    :param utc_time:
    :return:
    """
    # TODO: THIS IS AN ATROCIOUS SOLUTION
    return datetime.datetime.strptime(
        time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(float(utc_time))), "%Y/%m/%d %H:%M:%S")


client_id = '6JDbH-kgs4QjJA'
client_secret = '64KuekSKGSfbluwlQRX6x8kIXmw'
password = 'ihatemonopoly'
user_agent = 'testscript by /u/CP_bot'
username = 'BannedByLink'
reddit = RedditHelper(client_id, client_secret, password, user_agent, username)
reddit.build_connection()

if __name__ == "__main__":
    reddit.run_reddit_scraper()

