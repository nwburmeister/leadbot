import threading
import psutil
from app import logger
from app.scripts.reddit_reader import RedditReader
from app.scripts.main import parse_reddit_comments, auto_message
from app.scripts.reddit_tools import reddit
from app.scripts.email_reader import EmailReader


class EmailManager:

    def __init__(self):
        self.wanw = EmailReader(reddit)
        self.t_wanw = threading.Thread(target=self.wanw.run)
        self.t_wanw.daemon = True

        self.reddit_reader = RedditReader(reddit)
        self.t_replier = threading.Thread(target=self.reddit_reader.reply_checker)
        self.t_replier.daemon = True

    def start_wan_writer(self):
        self.t_wanw.start()

    def start_email_engine(self):
        self.t_replier.start()


class ThreadingManager:

    def __init__(self):
        self.t_scraper = threading.Thread(target=reddit.run_reddit_scraper)
        self.t_flagger = threading.Thread(target=parse_reddit_comments)

        self.t_scraper.daemon = True
        self.t_flagger.daemon = True


    def running(self):
        # cases could arise where on is alive and the other is not
        # TODO: handle above cases
        return self.t_scraper.is_alive() or self.t_flagger.is_alive()

    def start_thread_if_not_running(self):
        # starts threads if not already started, and returns whether threads were already started
        is_running = self.running() # copy
        if not is_running:
            self.t_flagger.start()
            self.flagger_id = self.t_flagger.ident
            self.t_scraper.start()
            self.scraper_id = self.t_scraper.ident
        else:
            logger.info("thread is running already")
        return is_running

    def start_auto_messenger(self, reddit, number_of_messages, sleep_time, message_content, subject_content, ca_auto_messenger_user):
        self.t_auto_messenger = threading.Thread(target=auto_message, args=(reddit, number_of_messages, sleep_time,
                                                                            message_content, subject_content, ca_auto_messenger_user))
        self.t_auto_messenger.daemon = True
        self.t_auto_messenger.start()
        self.auto_messenger_id = self.t_auto_messenger.ident


def check_pid(pid):
    """
    FUNCTION FOR CHECKING IF A PROCESS ID EXISTS

    :param pid:
    :return:
    """
    if psutil.pid_exists(pid):
        return True
    else:
        return False