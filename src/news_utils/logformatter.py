import logging

from scrapy import logformatter
from twisted.python.failure import Failure


class LogFormatter(logformatter.LogFormatter):
    """
    Overrides.
    - less verbose logging
    https://docs.scrapy.org/en/latest/topics/logging.html#scrapy.logformatter.LogFormatter
    """

    def dropped(self, *args, **kwargs):
        """
        Lower the logging level of dropped items from WARNING to DEBUG
        """
        # msg = "Dropped: %(exception)s"  # discard `item` from str format DROPPEDMSG
        # return {
        #     'level': logging.DEBUG,     # was logging.WARNING
        #     'msg': msg,                 # was 'msg': DROPPEDMSG,
        #     'args': {
        #         'exception': exception,
        #         # 'item': item,
        #     }
        # }
        fmt = super().dropped(*args, **kwargs)
        return fmt.update({'level': logging.DEBUG})

    def scraped(self, item, response, spider):
        """
        Logs a less verbose message when an item is scraped by a spider.
        """

        msg = "Scraped from %(src)s"
        if isinstance(response, Failure):
            src = response.getErrorMessage()
        else:
            src = response
        return {
            'level': logging.DEBUG,
            'msg': msg,                 # was 'msg': CRAWLEDMSG,
            'args': {
                'src': src,
                # 'item': item,
            }
        }
