import requests, os, sys, json, argparse, tempfile, traceback, random, time, math
from datetime import datetime, timedelta
from dateutil import parser as iso8601parser

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE_PATH = os.path.join(SCRIPT_PATH, 'config.json')
STATE_FILE_PATH = os.path.join(SCRIPT_PATH, 'state.json')
ACTIONS_FILE_PATH = os.path.join(SCRIPT_PATH, 'actions.json')
STR_ORGID = 'orgId'
STR_API_KEY = 'apiKey'
STR_LAST_EVENT_TIME = 'lastEventTime'
STR_ATLASSIAN = 'atlassian'

RESULTS_PER_REQUEST = 500
MAX_API_RETRIES = 5
MAX_REQUESTS_PER_MINUTE = 1
ATLASSIAN_APPLICATIONS = {
	'beacon': 'beacon',
	'bitbucket': 'bitbucket',
	'compass': 'compass',
	'confluence': 'confluence',
	'help center': 'jsm',
	'jsm': 'jsm',
	'jira': 'jira'
}

parser = argparse.ArgumentParser(description="Export Atlassian logs of various services such as Jira, Confluence, etc.")
parser.add_argument('--offset', '-o', dest='offset', required=False, default=24, type=int, help='maximum number of hours to go back in time')
parser.add_argument('--unread', '-u', dest='unread', action='store_true', help='export events but keep them marked as unread') 
args = parser.parse_args()

CONFIG = None
ACTIONS = None
RESULTS = tempfile.TemporaryFile(mode='w+')


def main():
	offset_time = datetime.now() - timedelta(hours = args.offset)
	offset_time = offset_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
	
	global CONFIG, ACTIONS
	CONFIG = load_config()
	ACTIONS = load_actions()
	earliest_time = load_state().get(STR_LAST_EVENT_TIME) or offset_time

	get_logs(earliest_time)
	if not args.unread:
		update_state()

	print_results()

	json_msg('extraction finished', 'extraction finished')


def load_config():
	"""loads the configuration and state

	Returns:
		 Dict:   A Dict object containing configuration.

	"""
	# Load config from the JSON file
	with open(CONFIG_FILE_PATH, 'r') as file:
		config = json.load(file)

	return config

def load_actions():
	"""loads the actions dictionary

	Returns:
		 Dict:   A Dict object containing information about actions.

	"""
	# Load config from the JSON file
	with open(ACTIONS_FILE_PATH, 'r') as file:
		actions = json.load(file)
	
	indexed_actions = {}

	for action in actions.get('data'):
		id = capitalize(dict_path(action, 'id'))

		application = ""
		for prefix, app in ATLASSIAN_APPLICATIONS.items():
			if id.startswith(prefix):
				application = app

		# TODO this uses only first type in the array as *the* type since Wazuh does not handle arrays
		actionType = dict_path(action, 'attributes', 'groupDisplayNames')
		if actionType:
			actionType = actionType[0].lower()
		else:
			actionType = 'undefined'

		indexed_actions[id] = {
			'id' : id,
			'actionType' : actionType,
			'application' : application
		}

	return indexed_actions


def get_logs(earliest_time):
	orgId = dict_path(CONFIG, STR_ORGID)
	apiKey = dict_path(CONFIG, STR_API_KEY)

	url = "https://api.atlassian.com/admin/v1/orgs/{}/events?limit={}&from={}".format(orgId, RESULTS_PER_REQUEST, as_epoch_millisec(earliest_time))
	headers = {
		"Accept": "application/json",
		"Authorization": "Bearer {}".format(apiKey)
	}

	nextPage = get_log_page(url, headers, earliest_time)

	while (nextPage):
		time.sleep(70)
		nextPage = get_log_page(nextPage, headers, earliest_time)


def dict_path(dictionary, *path):
	curr_element = dictionary

	for idx, key in enumerate(path):
		curr_element = curr_element.get(key)
		if (idx == len(path) - 1):
			break

		if (curr_element == None or not isinstance(curr_element, dict)):
			return None

	return curr_element


def get_retry(url, headers, retries):
	try:
		response = requests.request("GET", url, headers = headers)
		return json.loads(response.text)

	except:
		if (retries > 0):
			backoff = 2 ** (MAX_API_RETRIES - retries)
			time.sleep(backoff)

			return get_retry(url, headers, retries - 1)
		else:
			raise

def get_log_page(url, headers, earliest_time):
	results = get_retry(url, headers, MAX_API_RETRIES)

	if results.get('status'):
		fatal_error(json.dumps(results))
	
	for event in results.get('data', []):
		timestamp = dict_path(event, 'attributes', 'time')

		# search API returns "greater than or equal", but those that are equal were in previous run
		# so exclude them from the result
		if timestamp == earliest_time:
			continue

		converted_event = { }
		converted_event['srcip'] 		= dict_path(event, 'attributes', 'location', 'ip')
		converted_event['user'] 		= dict_path(event, 'attributes', 'actor', 'email')
		converted_event['id']           = dict_path(event, 'id')
		converted_event['timestamp']	= timestamp

		data = {  }
		converted_event[STR_ATLASSIAN] = data
		data['description']		= dict_path(event, 'message', 'content')
		data['actorId'] 		= dict_path(event, 'attributes', 'actor', 'id')
		data['orgId']      		= dict_path(CONFIG, STR_ORGID)
		data['action'] 			= capitalize(dict_path(event, 'attributes','action'))
		data['actionType']	 	= dict_path(ACTIONS, data['action'], 'actionType') or 'unknown'

		data['context'] = convert_dict(dict_path(event, 'attributes', 'context'))
		data['container'] = convert_dict(dict_path(event, 'attributes', 'container'))

		json.dump(converted_event, RESULTS, indent = None)
		RESULTS.write("\n")

	return dict_path(results, 'links', 'next')

def convert_dict(dict_array):
	converted_dict = {}

	if dict_array and len(dict_array) > 0:
		dict = dict_array[0]

		converted_dict['type'] = capitalize(dict_path(dict, 'type'))
		converted_dict['id'] = dict_path(dict, 'id')

		for key, value in dict_path(dict, 'attributes').items() or {}:				
			if (isinstance(value, __builtins__.dict)):
				converted_dict[key.lower()] = json.dumps(value)
			else:
				converted_dict[key.lower()] = value

	return converted_dict


def as_epoch_millisec(datetime):
	datetime = iso8601parser.parse(datetime)
	return str(math.trunc(datetime.timestamp() * 1000))

def log_entry(obj):
	return json.dumps(obj)

def capitalize(str):
	if str is None:
		return str
	else:
		return str.replace('_', ' ').lower()

def print_results():
	RESULTS.seek(0)

	for line in RESULTS:
		event = json.loads(line)
		print(log_entry(event))

def load_state():
	if not os.path.exists(STATE_FILE_PATH):
		return {}

	with open(STATE_FILE_PATH, 'r') as f:
		return json.load(f)

def save_state(state):
	with open(STATE_FILE_PATH + '.tmp', 'w+') as newfile:
		json.dump(state, newfile, indent = 3)
		newfile.write("\n")
		os.replace(newfile.name, STATE_FILE_PATH)


def update_state():
	state = load_state()
	last_event_time = state.setdefault(STR_LAST_EVENT_TIME, '1970-01-01T00:00:00.000Z')

	RESULTS.seek(0)

	for line in RESULTS:
		event = json.loads(line)
		eventTime = dict_path(event, 'timestamp')
		if (eventTime == None):
			warning('missing "timestamp" for event:\n{}'.format(event))

		if (last_event_time < eventTime):
				last_event_time = eventTime

	state[STR_LAST_EVENT_TIME] = last_event_time
	save_state(state)

def json_msg(action, description):
	msg = {
		'id' : random.randint(0, 99999999999999),
		'orgId' : dict_path(CONFIG, STR_ORGID),
		STR_ATLASSIAN : {
			'action' : action,
			'description' : description,
		}
	}

	print(log_entry(msg))


def fatal_error(message):
	json_msg('extraction error', message)

	sys.exit(0)   # not 1, otherwise the output will be ignored by Wazuh

def warning(message):
	json_msg('extraction warning', message)


if __name__ == '__main__':
	try:
		main()
	except Exception as exception:
		fatal_error("fatal exception :\n" + traceback.format_exc())
