import re
import datetime
import time
import email
import imaplib
import json
from app import logger
from itertools import chain
from app.models import Messages, db


class EmailReader:

    def __init__(self, reddit):

        # Restrict mail search. Be very specific.
        # Machine should be very selective to receive messages.
        self.reddit = reddit
        self.uid_max = 0
        self.imap_ssl_host = 'imap.gmail.com'
        self.imap_ssl_port = 993
        self.username = 'router@wallacemurry.com'
        self.password = 'assaultedQuails'


    @staticmethod
    def search_string(uid_max, criteria):
        # Produce search string in IMAP format:
        #   e.g. (FROM "me@gmail.com" SUBJECT "abcde" BODY "123456789" UID 9999:*)
        c = list(map(lambda t: (t[0], '"'+str(t[1])+'"'), criteria.items())) + [('UID', '%d:*' % (uid_max+1))]
        return '(%s)' % ' '.join(chain(*c))

    @staticmethod
    def get_first_text_block(msg):
        type = msg.get_content_maintype()

        if type == 'multipart':
            for part in msg.get_payload():
                if part.get_content_maintype() == 'text':
                    return part.get_payload()
        elif type == 'text':
            print("content maintype is text")
            return msg.get_payload()

    def run(self):
        """

        :return:
        """
        logger.info("ENTERED EMAIL INBOX SCRAPER")
        while True:
            # CONNECT TO EMAIL SERVER
            try:
                # TRY TO LOGIN
                self.server = imaplib.IMAP4_SSL(self.imap_ssl_host, self.imap_ssl_port)
                self.server.login(self.username, self.password)
            except Exception:
                logger.critical("FAILED TO LOGIN TO EMAIL SERVER. KILLING THREAD")
                # exit(1)
            self.server.select('INBOX')
            (retcode, messages) = self.server.search(None, '(UNSEEN)')
            if retcode == 'OK':
                for num in messages[0].split():
                    typ, data = self.server.fetch(num, '(RFC822)')
                    for response_part in data:
                        if isinstance(response_part, tuple):
                            message = email.message_from_bytes(response_part[1])
                            _from = message['Reply-to']
                            _subject = message['Subject']
                            if 're' in _subject.lower():
                                _subject = re.split("Re:", _subject)[1].strip()
                            _subject = json.loads(_subject)
                            mesage_id = _subject['message_id']
                            # EXTRACT REDDIT USERNAME
                            reddit_user = _subject['username']
                            body = EmailReader.get_first_text_block(message)
                            try:
                                # MESSAGE HAS A SIGNATURE, ALSO A POSSIBLE REPLY W SIGNATURE
                                body_without_signature = body.split("=E2=80=94")[1]
                            except IndexError:
                                # MESSAGE IS A REPLY
                                body_without_signature = body.split("=EF=BB=BF")[0]

                            # parent_message = Messages.query.filter_by(
                            #     recipient=reddit_user).filter_by(
                            #     ca_user_id_assoc='parent').first()

                            self.reddit.reddit_conn.inbox.message(mesage_id).reply(body_without_signature)

                            self.server.store(num, '+FLAGS', '\\Seen')
                            message = Messages(sender=_from,
                                               recipient=reddit_user,
                                               subject=_subject['subject'],
                                               body=body_without_signature,
                                               date_sent=datetime.datetime.now(),
                                               has_been_sent_for_processing=1,
                                               ca_user_id_assoc=mesage_id)
                            Messages.add_record(message)
                            db.session.commit()
            self.server.logout()
            # logger.info("NOTHING NEW IN EMAIL INBOX--SLEEPING")
            time.sleep(20)