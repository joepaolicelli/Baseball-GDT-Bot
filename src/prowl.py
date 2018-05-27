# interface with Prowl for notifications

import logging

class Prowl:
    def __init__(self, apiKey=None, teamName=None):
        self.apiKey = apiKey
        self.appName = teamName + " Reddit Bot"

    def verify_key(self, apiKey=None):
       if apiKey == None: apiKey=self.apiKey
       return self.api_call('verify',{},apiKey)

    def send_notification(self, event, description, apiKey=None, priority=0, url=None, appName=None):
        if appName == None: appName=self.appName
        if apiKey == None: apiKey=self.apiKey

        data = {'event':event, 'description':description, 'priority':priority, 'application':appName, 'apikey':apiKey}
        if url: data.update({'url':url})
        return self.api_call('add',data,apiKey)

    def api_call(self, action, data, apiKey=None):
        if apiKey == None: apiKey=self.apiKey

        import urllib2, urllib
        url = 'https://api.prowlapp.com/publicapi/'+action
        if action=='verify': url += "?apikey="+apiKey

        encodedData = urllib.urlencode(data)
        logging.debug("Making API call to Prowl (%s) with data: %s",url, encodedData)
        try:
            req = urllib2.Request(url=url,data=encodedData)
            response = urllib2.urlopen(req).read()
        except urllib2.HTTPError as e:
            response = {'status':'error', 'code':str(e.code), 'message':e.reason}
        except urllib2.URLError as e:
            response = {'status':'error', 'code':str(e.code), 'message':e.reason}
        except Exception as e:
            response = {'status':'error', 'code':'-1', 'message':'Unknown error', 'errMsg':e}
            
        return self.parse_response(response)

    def parse_response(self, response):
        import xml.etree.ElementTree as ET
        import simplejson as json

        errorMessages = {   
                            '-1' : 'Unknown error',
                            '200': 'Success',
                            '400': 'Bad request, the parameters you provided did not validate.',
                            '401': 'Not authorized, the API key given is not valid, and does not correspond to a user.',
                            '406': 'Not acceptable, your IP address has exceeded the API limit.',
                            '409': 'Not approved, the user has yet to approve your retrieve request.',
                            '500': 'Internal server error, something failed to execute properly on the Prowl side.'
                        }

        if isinstance(response,dict):
            if not response.get('errMsg',None): response.update({'errMsg':errorMessages[response.get('code')]})
            return response
            
        root = ET.fromstring(response)
        child = root[0]
        parsedResponse = {}
        parsedResponse.update({'status':child.tag, 'message':child.text, 'errMsg':errorMessages[child.get('code')]})
        for key,val in child.attrib.items():
            parsedResponse.update({key:val})

        return parsedResponse
