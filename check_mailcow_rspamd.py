#! /usr/bin/env python3
# -*- coding: utf-8; py-indent-offset: 4 -*-
#
# Author:  Andreas Bucher
# Contact: icinga (at) buchermail (dot) de
#          
# License: The Unlicense, see LICENSE file.

# https://github.com/anbucher/check_mailcow_rspamd.git

"""Have a look at the check's README for further details.
"""
import argparse
from difflib import diff_bytes
import sys
import json
import operator
import collections
import time
import requests
from requests.structures import CaseInsensitiveDict
from traceback import format_exc

__author__ = 'Andreas Bucher'
__version__ = '2023010901'


DESCRIPTION = """This plugin lets you check the mailcow rspamd stats"""

# Sample URL: https://mailcow.example.com/api/v1/get/logs/rspamd-history
DEFAULT_API_PATH = '/api/v1/get/logs/rspamd-history'

# Count of Logs that should be returned
DEFAULT_HISTORY_COUNT = 400
DEFAULT_MIN_BACK = 5

# Time where no incoming mail detected
DEFAULT_WARN = 1800 # seconds
DEFAULT_CRIT = 3600 # seconds


## Define states

# STATE_OK = 0: The plugin was able to check the service and it appeared
# to be functioning properly.

# STATE_WARN = 1: The plugin was able to check the service, but it
# appeared to be above some "warning" threshold or did not appear to be
# working properly.

# STATE_CRIT = 2: The plugin detected that either the service was not
# running or it was above some "critical" threshold.

# STATE_UNKNOWN = 3: Invalid command line arguments were supplied to the
# plugin or low-level failures internal to the plugin (such as unable to
# fork, or open a tcp socket) that prevent it from performing the
# specified operation. Higher-level errors (such as name resolution
# errors, socket timeouts, etc) are outside of the control of plugins and
# should generally NOT be reported as UNKNOWN states.

# Author of state definition
# __author__ = 'Andreas Bucher'
# __version__ = '2023010901'


STATE_OK = 0
STATE_WARN = 1
STATE_CRIT = 2
STATE_UNKNOWN = 3
#STATE_DEPENDENT = 4

########### common functions ###########
# useful functions - Copyright by https://git.linuxfabrik.ch/linuxfabrik/lib/-/blob/master/base3.py

def get_perfdata(label, value, uom, warn, crit, min, max):
    """Returns 'label'=value[UOM];[warn];[crit];[min];[max]
    """
    msg = "'{}'={}".format(label, value)
    if uom is not None:
        msg += uom
    msg += ';'
    if warn is not None:
        msg += str(warn)
    msg += ';'
    if crit is not None:
        msg += str(crit)
    msg += ';'
    if min is not None:
        msg += str(min)
    msg += ';'
    if max is not None:
        msg += str(max)
    msg += ' '
    return msg


def oao(msg, state=STATE_OK, perfdata='', always_ok=False):
    """Over and Out (OaO)

    Print the stripped plugin message. If perfdata is given, attach it
    by `|` and print it stripped. Exit with `state`, or with STATE_OK (0) if
    `always_ok` is set to `True`.
    """
    if perfdata:
        print(msg.strip() + '|' + perfdata.strip())
    else:
        print(msg.strip())
    if always_ok:
        sys.exit(0)
    sys.exit(state)



def coe(result, state=STATE_UNKNOWN):
    """Continue or Exit (CoE)

    This is useful if calling complex library functions in your checks
    `main()` function. Don't use this in functions.

    If a more complex library function, for example `lib.url3.fetch()` fails, it
    returns `(False, 'the reason why I failed')`, otherwise `(True,
    'this is my result'). This forces you to do some error handling.
    To keep things simple, use `result = lib.base3.coe(lib.url.fetch(...))`.
    If `fetch()` fails, your plugin will exit with STATE_UNKNOWN (default) and
    print the original error message. Otherwise your script just goes on.

    The use case in `main()` - without `coe`:

    >>> success, html = lib.url3.fetch(URL)
    >>> if not success:
    >>>     print(html)             # contains the error message here
    >>>>    exit(STATE_UNKNOWN)

    Or simply:

    >>> html = lib.base3.coe(lib.url.fetch(URL))

    Parameters
    ----------
    result : tuple
        The result from a function call.
        result[0] = expects the function return code (True on success)
        result[1] = expects the function result (could be of any type)
    state : int
        If result[0] is False, exit with this state.
        Default: 3 (which is STATE_UNKNOWN)

    Returns
    -------
    any type
        The result of the inner function call (result[1]).
"""

    if result[0]:
        # success
        return result[1]
    print(result[1])
    sys.exit(state)

def get_table(data, cols, header=None, strip=True, sort_by_key=None, sort_order_reverse=False):
    """Takes a list of dictionaries, formats the data, and returns
    the formatted data as a text table.
    Required Parameters:
        data - Data to process (list of dictionaries). (Type: List)
        cols - List of cols in the dictionary. (Type: List)
    Optional Parameters:
        header - The table header. (Type: List)
        strip - Strip/Trim values or not. (Type: Boolean)
        sort_by_key - The key to sort by. (Type: String)
        sort_order_reverse - Default sort order is ascending, if
            True sort order will change to descending. (Type: bool)
    Inspired by
    https://www.calazan.com/python-function-for-displaying-a-list-of-dictionaries-in-table-format/
    """
    if not data:
        return ''

    # Sort the data if a sort key is specified (default sort order is ascending)
    if sort_by_key:
        data = sorted(data,
                      key=operator.itemgetter(sort_by_key),
                      reverse=sort_order_reverse)

    # If header is not empty, create a list of dictionary from the cols and the header and
    # insert it before first row of data
    if header:
        header = dict(zip(cols, header))
        data.insert(0, header)

    # prepare data: decode from (mostly) UTF-8 to Unicode, optionally strip values and get
    # the maximum length per column
    column_widths = collections.OrderedDict()
    for idx, row in enumerate(data):
        for col in cols:
            try:
                if strip:
                    data[idx][col] = str(row[col]).strip()
                else:
                    data[idx][col] = str(row[col])
            except:
                return 'Unknown column "{}"'.format(col)
            # get the maximum length
            try:
                column_widths[col] = max(column_widths[col], len(data[idx][col]))
            except:
                column_widths[col] = len(data[idx][col])

    if header:
        # Get the length of each column and create a '---' divider based on that length
        header_divider = []
        for col, width in column_widths.items():
            header_divider.append('-' * width)

        # Insert the header divider below the header row
        header_divider = dict(zip(cols, header_divider))
        data.insert(1, header_divider)

    # create the output
    table = ''
    cnt = 0
    for row in data:
        tmp = ''
        for col, width in column_widths.items():
            if cnt != 1:
                tmp += '{:<{}} ! '.format(row[col], width)
            else:
                # header row
                tmp += '{:<{}}-+-'.format(row[col], width)
        cnt += 1
        table += tmp[:-2] + '\n'

    return table

########### specific check functions ###########

def parse_args():
    """Parse command line arguments using argparse.
    """
    parser = argparse.ArgumentParser(description=DESCRIPTION)

    parser.add_argument(
        '-V', '--version',
        action='version',
        version='%(prog)s: v{} by {}'.format(__version__, __author__)
    )

    parser.add_argument(
        '--always-ok',
        help='Always returns OK.',
        dest='ALWAYS_OK',
        action='store_true',
        default=False,
    )

    parser.add_argument(
        '--server',
        help='Server address of your mailcow instance.',
        dest='SERVER_ADDRESS',
        required=True
    )

    parser.add_argument(
        '--count',
        help='Count of Log entries that should be returned. Default: %(default)s',
        dest='HISTORY_COUNT',
        default=DEFAULT_HISTORY_COUNT,
    )

    parser.add_argument(
        '--minBack',
        help='number of minutes to look back in logs. Default: %(default)s',
        dest='MIN_BACK',
        default=DEFAULT_MIN_BACK,
    )

    parser.add_argument(
        '-c', '--critical',
        help='Set the critical threshold seconds since last connection update. Default: %(default)s',
        dest='CRIT',
        type=int,
        default=DEFAULT_CRIT,
    )

    parser.add_argument(
        '-w', '--warning',
        help='Set the warning threshold  seconds since last connection update. Default: %(default)s',
        dest='WARN',
        type=int,
        default=DEFAULT_WARN,
    )

    parser.add_argument(
        '--apiKey',
        help='Mailcow apiKey. Can be generated in Mailcow UI',
        dest='API_KEY',
        default='',
        required=True,
    )


    return parser.parse_args()


def run_api_request(path, apiKey):
    """Check Rspamd API.
    """
    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"
    headers["X-API-Key"] = apiKey


    # Get History from Rspamd API
    try:
        j = requests.get(path, headers=headers)
        json_str = j.json()

    except Exception as ex:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        msg = template.format(type(ex).__name__, ex.args)
        return(False, msg)

    #FAKE request
    # f = open("sample_data/response.json", encoding='UTF-8')
    # json_str = json.load(f)

    try:
        return (True, json_str)
    except:
        return(False, 'ValueError: No JSON object could be decoded')

def get_sec_last_mail(data):
    """Read out seconds since last mail received.
    """
    # Get current unix timestamp
    now = int(time.time()) 

    # Check date difference
    try:
        ### timeFormat: 1672920848
        lastMailReceived = int(data[0]['unix_time'])
        # calculate time difference
        diffInSecs = (abs(now - lastMailReceived ))

        return (True, diffInSecs)
    except:
        return (False, 'ValueError: Last Mail time could not be parsed') 

def get_metrics(data, minBack):

    # calculate different action count
    metrics = {
        'throughput24h': 0,
        'reject': 0,
        'soft reject': 0,
        'rewrite subject': 0,
        'add header': 0,
        'greylist': 0,
        'no action': 0,
        'total': 0
    }

    incoming = {}
    outgoing = {}

    try:

        now = int(time.time()) 

        for mail in data:

            # calc timedifference for current mail
            mailReceived = int(mail['unix_time'])
            diffInSecs = (abs(now - mailReceived ))

            # check applied action
            action = mail['action']

            # timeframe for 24h throughput / spam ratio
            if diffInSecs < (24*60*60):
                metrics['throughput24h'] += 1

                # Spam Ratio Calculation
                # incoming
                if mail['user'] == 'unknown' and len(mail['rcpt_smtp']) > 0:

                    d = incoming
                    user = str(mail['rcpt_smtp'][0]).lower()
                # outgoing
                elif mail['user'] != 'unknown':
                    d = outgoing
                    user = mail['user']

                # check action
                if action== 'no action' :
                    category = 'ham'
                elif action != 'greylist' and action != 'soft reject':
                    category = 'spam'
                else:
                    continue                    

                # check if user exists
                if user not in d:
                    d[user] = {
                        'spam': 0, 
                        'ham': 0,
                        'total': 0,
                        'ratio': 1
                    }

                d[user][category]+= 1
                d[user]['total'] = d[user]['spam'] + d[user]['ham']
                d[user]['ratio'] = 1 - (d[user]['ham'] / d[user]['total'])



            # check if mail is within given timeframe           
            if diffInSecs < int(minBack) * 60:
                
                # check action and count
                if(action):
                    if action in metrics:
                        metrics[action] += 1
                    else:
                        metrics[action] = 1
                    
                    if 'total' in metrics:
                        metrics['total'] += 1
                    else: 
                        metrics['total'] = 1

        # sort spam ratio dicts and assign to metrics
        incomingTop10 = sorted(incoming.items(), reverse = True, key = lambda x: x[1]['total'])[0:10]
        outgoingTop10 = sorted(outgoing.items(), reverse = True, key = lambda x: x[1]['total'])[0:10]
        metrics['incomingTop10BySpamRatio'] = sorted(incomingTop10, reverse = True, key = lambda x: x[1]['ratio'])
        metrics['outgoingTop10BySpamRatio'] = sorted(outgoingTop10, reverse = True, key = lambda x: x[1]['ratio'])

        return (True, metrics)
    except Exception as ex:
        return (False, 'ValueError: Metrics could not be parsed') 

def main():
    """The main function. Hier spielt die Musik.
    """

    # parse the command line, exit with UNKNOWN if it fails
    try:
        args = parse_args()
    except SystemExit:
        sys.exit(STATE_UNKNOWN)

    # init output vars
    msg = ''
    state = STATE_OK
    perfdata = ''
    table_values = []

    # Build API path
    path = args.SERVER_ADDRESS + DEFAULT_API_PATH + '/' + str(DEFAULT_HISTORY_COUNT)

    response = coe(run_api_request(path, args.API_KEY))
    diffSecs = coe(get_sec_last_mail(response))
    metrics = coe(get_metrics(response, args.MIN_BACK))

    # Add metrics to perfdata
    perfdata += get_perfdata('total', metrics['total'], None, None, None, 0, None)
    perfdata += get_perfdata('throughput24h', metrics['throughput24h'], None, None, None, 0, None)
    perfdata += get_perfdata('reject', metrics['reject'], None, None, None, 0, None)
    perfdata += get_perfdata('soft reject', metrics['soft reject'], None, None, None, 0, None)
    perfdata += get_perfdata('rewrite subject', metrics['rewrite subject'], None, None, None, 0, None)
    perfdata += get_perfdata('add header', metrics['add header'], None, None, None, 0, None)
    perfdata += get_perfdata('greylist', metrics['greylist'], None, None, None, 0, None)
    perfdata += get_perfdata('no action', metrics['no action'], None, None, None, 0, None)

    # Add Top5 Spam Ratio Users
    for user in metrics['incomingTop10BySpamRatio']:
        table_values.append({
            'name': user[0],     # https://github.com/Linuxfabrik/monitoring-plugins/issues/586
            'spamRatio': '{:.2f}'.format(round(user[1]['ratio'],4)*100),
            'mailsTotal': '{}'.format(user[1]['total']),
            })


    # check warn and crit thresholds
    try:
        if diffSecs > args.CRIT:
            msg += 'CRIT threshold reached: ' + str(diffSecs)
            state = STATE_CRIT
        else:    
            if diffSecs > args.WARN:
                msg += 'WARN threshold reached: ' + str(diffSecs)
                state = STATE_WARN
            else:
                msg = 'OK - ' + str(diffSecs) + 's since last mail'
                msg += '\nThroughput: {} messages/day'.format(metrics['throughput24h'])
                msg += '\nIncoming 24h Stats:'
                msg += '\n' + get_table(
                    table_values,
                    ['name', 'spamRatio', 'mailsTotal'],
                    header=['Recipient', 'Spam %', 'Mails Total '],
                    )
                state = STATE_OK

    except Exception as ex:
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        msg = template.format(type(ex).__name__, ex.args)
        state = STATE_UNKNOWN
        
    # 
    # TODO: get perf values  from metrics (rxfw, ackr)

    oao(msg, state, perfdata)

if __name__ == '__main__':
    try:
        main()
    except Exception:   # pylint: disable=W0703
        """See you (cu)

        Prints a Stacktrace (replacing "<" and ">" to be printable in Web-GUIs), and exits with
        STATE_UNKNOWN.
        """
        print(format_exc().replace("<", "'").replace(">", "'"))
        sys.exit(STATE_UNKNOWN)
