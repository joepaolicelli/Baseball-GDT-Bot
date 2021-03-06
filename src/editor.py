# does all the post generating and editing

import player

import xml.etree.ElementTree as ET
import urllib2
import simplejson as json
from datetime import datetime, timedelta
import pytz as tz
import tzlocal
import time
import games as gamesModule

class Editor:

    games = gamesModule.Games().games
    gamesLive = gamesModule.Games().gamesLive

    def __init__(self,settings):
        self.SETTINGS = settings
        self.TEAMINFO = {}

    def api_download(self,link,critical=True,sleepTime=10,forceDownload=False,localWait=4,apiVer=None):
        usecache=False
        if apiVer:
            link = '/api/' + apiVer + link[link.find('/',link.find('/api/')+5):]
            if self.SETTINGS.get('LOG_LEVEL')>3: print "updated api link per apiVer param:",link
        if self.gamesLive.get(link) and (self.gamesLive.get(link).get('metaData',{}).get('timeStamp') or self.gamesLive.get(link).get('localTimestamp')) and not forceDownload:
            ts = self.gamesLive.get(link).get('metaData',{}).get('timeStamp',datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
            wait = self.gamesLive.get(link).get('metaData',{}).get('wait','-1')
            if self.SETTINGS.get('LOG_LEVEL')>3: print "api wait time:",datetime.strptime(ts,"%Y%m%d_%H%M%S") + timedelta(seconds=int(wait))," // current time:",datetime.utcnow()," // use cache (api wait): ",datetime.strptime(ts,"%Y%m%d_%H%M%S") + timedelta(seconds=int(wait)) > datetime.utcnow()," // use cache (local wait):",self.gamesLive.get(link).get('localTimestamp') + timedelta(seconds=localWait) > datetime.utcnow()
            if (ts and wait and datetime.strptime(ts,"%Y%m%d_%H%M%S") + timedelta(seconds=int(wait)) > datetime.utcnow()) or (self.gamesLive.get(link).get('localTimestamp') and self.gamesLive.get(link).get('localTimestamp') + timedelta(seconds=localWait) > datetime.utcnow()):
                if self.SETTINGS.get('LOG_LEVEL')>3: print "Using cached data for",link,"..."
                usecache = True
        if not usecache:
            if forceDownload:
                if self.SETTINGS.get('LOG_LEVEL')>3: print "Forcing downloading of",link,"from MLB API..."
            else:
                if self.SETTINGS.get('LOG_LEVEL')>3: print "Downloading",link,"from MLB API..."
            while True:
                try:
                    api_response = urllib2.urlopen(self.SETTINGS.get('apiURL') + link)
                    self.gamesLive.update({link : json.load(api_response)})
                    self.gamesLive[link].update({'localTimestamp' : datetime.utcnow(),'localWait' : localWait})
                    break
                except urllib2.HTTPError, e:
                    if critical:
                        if self.SETTINGS.get('LOG_LEVEL')>0: print "ERROR: Couldn't download",link,"from MLB API:",e,": retrying in",sleepTime,"seconds..."
                        time.sleep(sleepTime)
                    else:
                        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Couldn't download",link,"from MLB API:",e,": continuing in",sleepTime,"seconds..."
                        time.sleep(sleepTime)
                        break
                except urllib2.URLError, e:
                    if critical:
                        if self.SETTINGS.get('LOG_LEVEL')>0: print "ERROR: Couldn't connect to MLB API to download",link,":",e,": retrying in",sleepTime,"seconds..."
                        time.sleep(sleepTime)
                    else:
                        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Couldn't connect to MLB API to download",link,":",e,": continuing in",sleepTime,"seconds..."
                        time.sleep(sleepTime)
                        break
                except Exception, e:
                    if critical:
                        if self.SETTINGS.get('LOG_LEVEL')>0: print "ERROR: Unknown error downloading",link," from MLB API:",e,": retrying in",sleepTime,"seconds..."
                        time.sleep(sleepTime)
                    else:
                        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Unknown error downloading",link," from MLB API:",e,": continuing in",sleepTime,"seconds..."
                        time.sleep(sleepTime)
                        break
        return self.gamesLive.get(link)

    def get_schedule(self,day,team_id=None):
        todayurl = "/api/v1/schedule?language=en&sportId=1&date=" + day.strftime("%m/%d/%Y")
        if team_id: todayurl += "&teamId=" + str(team_id)

        todaydata = self.api_download(todayurl,True,30)
        todaydates = todaydata['dates']
        if len(todaydates) == 0: todaygames = {}
        else: todaygames = todaydates[next((i for i,x in enumerate(todaydates) if x.get('date') == day.strftime('%Y-%m-%d')), 0)].get('games')

        if len(todaygames) == 0:
            if self.SETTINGS.get('LOG_LEVEL')>1: print datetime.strftime(datetime.today(), "%d %I:%M:%S %p"), "There are no games on",day.strftime("%m/%d/%Y")
            todaygames = {}

        if isinstance(todaygames,dict): todaygames = [todaygames]
        return todaygames

    def replace_params(self,original,thread,type,k=None,timemachine=False,myteamwon=""):
        if self.SETTINGS.get('LOG_LEVEL')>2: print "Replacing parameters in",thread,type + "..."
        replaced = original.replace('\{','PLACEHOLDEROPEN').replace('\}','PLACEHOLDERCLOSE').replace('\:','PLACEHOLDERCOLON').replace('\%','PLACEHOLDERMOD')
        while replaced.find('{') != -1:
            modifier = None
            replaceVal = ""
            if replaced.find('}') < replaced.find('{'):
                if replaced.find('}') == -1:
                    if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Extra { or missing } detected in",thread,type,"at character",str(replaced.find('{')),"- escaping the {..."
                    replaced = replaced[0:replaced.find('{')] + 'PLACEHOLDEROPEN' + replaced[replaced.find('{')+1:]
                else:
                    if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Detected } before { in",thread,type,"at character",str(replaced.find('}')),"- escaping the }..."
                    replaced = replaced[0:replaced.find('}')] + 'PLACEHOLDERCLOSE' + replaced[replaced.find('}')+1:]
                continue
            paramParts = [replaced.find('{'), replaced.find('}'), replaced[replaced.find('{')+1:replaced.find('}')], replaced[replaced.find('{'):replaced.find('}')+1]]
            if paramParts[2].find('%') != -1 and not paramParts[2].startswith('date') \
                and not paramParts[2].startswith('dh') and not paramParts[2].startswith('series') \
                and not paramParts[2].startswith('link'):
            #modifier detected - can't modify params that take custom format with variables
                modifier = paramParts[2][paramParts[2].find('%')+1:] #extract modifier, remove from param parts, then apply the modifier later
                paramParts[2] = paramParts[2].replace('%'+modifier,'')
            if paramParts[2].find('{') != -1:
                if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Extra { detected in",thread,type,"at character",str(replaced.find('{')),"- escaping it..."
                replaced = replaced[0:replaced.find('{')] + 'PLACEHOLDEROPEN' + replaced[replaced.find('{')+1:]
                continue
            if not paramParts[2]:
                if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Empty parameter {} detected in",thread,type,"at characters",str(replaced.find('{')),"and",str(replaced.find('}')),"- escaping both { and }..."
                replaced = replaced[0:replaced.find('{')] + 'PLACEHOLDEROPEN' + replaced[replaced.find('{')+1:]
                replaced = replaced[0:replaced.find('}')] + 'PLACEHOLDERCLOSE' + replaced[replaced.find('}')+1:]
                continue
            if paramParts[2].find(':') != -1: #need to further split param
                paramParts.append(paramParts[2][:paramParts[2].find(':')])
                paramParts.append(paramParts[2][paramParts[2].find(':')+1:])
                if self.SETTINGS.get('LOG_LEVEL')>2: print "Found param parts:",paramParts
                if paramParts[4] == 'date':
                    if thread == 'off':
                        replaceVal = datetime.now().strftime(paramParts[5])
                    else:
                        replaceVal = self.games[k].get('gameInfo').get('date_object').strftime(paramParts[5])
                elif paramParts[4] == 'myTeam':
                    if paramParts[5] == 'wins':
                        if thread == 'off': #TODO: wins currently not supported for off thread, because this value comes from the game data
                            if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'myTeam:wins' parameter is currently not supported for off day thread",type+", using 0..."
                            replaceVal =  "0"
                        else:
                            if timemachine and myteamwon=="1":
                                replaceVal = str(int(self.games[k].get('gameInfo').get(self.games[k].get('homeaway'),{}).get('win'))-1)
                            else:
                                replaceVal = str(self.games[k].get('gameInfo').get(self.games[k].get('homeaway'),{}).get('win'))
                    elif paramParts[5] == 'losses':
                        if thread == 'off': #TODO: losses currently not supported for off thread, because this value comes from the game data
                            if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'myTeam:losses' parameter is currently not supported for off day thread",type+", using 0..."
                            replaceVal =  "0"
                        else:
                            if timemachine and myteamwon=="0":
                                replaceVal = str(int(self.games[k].get('gameInfo').get(self.games[k].get('homeaway'),{}).get('loss'))-1)
                            else:
                                replaceVal = str(self.games[k].get('gameInfo').get(self.games[k].get('homeaway'),{}).get('loss'))
                    elif paramParts[5] == 'runs':
                        if thread != 'post': #runs only supported for post thread/tweet
                            if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'myTeam:runs' parameter is only supported for postgame thread, using 0..."
                            replaceVal =  "0"
                        else:
                            replaceVal =  str(self.games[k].get('gameInfo').get(self.games[k].get('homeaway'),{}).get('runs'))
                    else:
                        replaceVal =  self.lookup_team_info(paramParts[5],'team_code',self.SETTINGS.get('TEAM_CODE')) #don't need to pass sportCode in this call, since myTeam must be MLB
                elif paramParts[4] == 'oppTeam':
                    if thread == 'off':
                        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'oppTeam' parameter is not supported for off day thread",type,"(only myTeam), removing..."
                        replaceVal = ''
                    else:
                        if self.games[k].get('homeaway') == 'home': opp = 'away'
                        else: opp = 'home'
                        if paramParts[5] == 'wins':
                            if timemachine and myteamwon=="0":
                                replaceVal = str(int(self.games[k].get('gameInfo').get(opp).get('win'))-1)
                            else:
                                replaceVal =  str(self.games[k].get('gameInfo').get(opp).get('win'))
                        elif paramParts[5] == 'losses':
                            if timemachine and myteamwon=="1":
                                replaceVal =  str(int(self.games[k].get('gameInfo').get(opp).get('loss'))-1)
                            else:
                                replaceVal =  str(self.games[k].get('gameInfo').get(opp).get('loss'))
                        elif paramParts[5] == 'runs':
                            if thread != 'post': #runs only supported for post thread/tweet
                                if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'oppTeam:runs' parameter is only supported for postgame thread, using 0..."
                                replaceVal =  "0"
                            else:
                                replaceVal =  str(self.games[k].get('gameInfo').get(opp).get('runs'))
                        else:
                            replaceVal =  self.lookup_team_info(paramParts[5],'team_id',str(self.games[k].get('teams').get(opp).get('team').get('id')),self.games[k].get('gameInfo').get(opp).get('sport_code'))
                elif paramParts[4] == 'awayTeam':
                    if thread == 'off':
                        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'awayTeam' parameter is not supported for off day thread",type,"(only myTeam), removing..."
                        replaceVal =  ''
                    else:
                        if paramParts[5] == 'wins':
                            if timemachine and ((myteamwon=="1" and self.games[k].get('homeaway')=='away') or (myteamwon=="0" and self.games[k].get('homeaway')=='home')):
                                replaceVal =  str(int(self.games[k].get('gameInfo').get('away').get('win'))-1)
                            else:
                                replaceVal =  str(self.games[k].get('gameInfo').get('away').get('win'))
                        elif paramParts[5] == 'losses':
                            if timemachine and ((myteamwon=="0" and self.games[k].get('homeaway')=='away') or (myteamwon=="1" and self.games[k].get('homeaway')=='home')):
                                replaceVal =  str(int(self.games[k].get('gameInfo').get('away').get('loss'))-1)
                            else:
                                replaceVal =  str(self.games[k].get('gameInfo').get('away').get('loss'))
                        elif paramParts[5] == 'runs':
                            if thread != 'post': #runs only supported for post thread/tweet
                                if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'awayTeam:runs' parameter is only supported for postgame thread, using 0..."
                                replaceVal =  "0"
                            else:
                                replaceVal =  str(self.games[k].get('gameInfo').get('away').get('runs'))
                        else:
                            replaceVal =  self.lookup_team_info(paramParts[5],'team_id',str(self.games[k].get('teams').get('away').get('team').get('id')),self.games[k].get('gameInfo').get('away').get('sport_code'))
                elif paramParts[4] == 'homeTeam':
                    if thread == 'off':
                        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'homeTeam' parameter is not supported for off day thread",type,"(only myTeam), removing..."
                        replaceVal =  ''
                    else:
                        if paramParts[5] == 'wins':
                            if timemachine and ((myteamwon=="1" and self.games[k].get('homeaway')=='home') or (myteamwon=="0" and self.games[k].get('homeaway')=='away')):
                                replaceVal =  str(int(self.games[k].get('gameInfo').get('home').get('win'))-1)
                            else:
                                replaceVal =  str(self.games[k].get('gameInfo').get('home').get('win'))
                        elif paramParts[5] == 'losses':
                            if timemachine and ((myteamwon=="0" and self.games[k].get('homeaway')=='home') or (myteamwon=="1" and self.games[k].get('homeaway')=='away')):
                                replaceVal =  str(int(self.games[k].get('gameInfo').get('home').get('loss'))-1)
                            else:
                                replaceVal =  str(self.games[k].get('gameInfo').get('home').get('loss'))
                        elif paramParts[5] == 'runs':
                            if thread != 'post': #runs only supported for post thread/tweet
                                if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'homeTeam:runs' parameter is only supported for postgame thread, using 0..."
                                replaceVal =  "0"
                            else:
                                replaceVal =  str(self.games[k].get('gameInfo').get('home').get('runs'))
                        else:
                            replaceVal =  self.lookup_team_info(paramParts[5],'team_id',str(self.games[k].get('teams').get('home').get('team').get('id')),self.games[k].get('gameInfo').get('home').get('sport_code'))
                elif paramParts[4] == 'series':
                    if thread == 'off':
                        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'series' parameter is not supported for off day thread",type+", removing..."
                        replaceVal =  ''
                    else:
                        if self.games[k].get('gameType') in ['I', 'E', 'S','R']:
                            if self.SETTINGS.get('LOG_LEVEL')>2: print "{series} parameter only applies to post season games, removing..."
                            replaceVal =  ''
                        else:
                            series = paramParts[5].replace('%D',self.games[k].get('seriesDescription')).replace('%N',str(self.games[k].get('seriesGameNumber')))
                            replaceVal = series
                elif paramParts[4] == 'dh':
                    if thread == 'off':
                        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: 'dh' parameter is not supported for off day thread",type+", removing..."
                        replaceVal =  ''
                    else:
                        if self.games[k].get('doubleHeader') == 'N':
                            if self.SETTINGS.get('LOG_LEVEL')>2: print "{dh} parameter only applies to doubleheader games, removing..."
                            replaceVal =  ''
                        else:
                            dh = paramParts[5].replace('%N',str(self.games[k].get('gameNumber')))
                            replaceVal = dh
                else: #there are no other supported parameters with multiple parts at this time
                    if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Unsupported parameter",paramParts[3],"found in",thread,type+", removing..."
                    replaceVal =  ''
            else: #params that don't have multiple parts
                if self.SETTINGS.get('LOG_LEVEL')>2: print "Found title param parts:",paramParts
                if paramParts[2] == 'vsat': 
                    if thread == "off": 
                        replaceVal =  ''
                        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: {vsat} parameter is not supported for off day thread",type+", removing..."
                    else:
                        if self.games[k].get('homeaway') == 'home': vsat = "vs"
                        else: vsat = '@'
                        replaceVal =  vsat
                elif paramParts[2] == 'date': #use default date format
                    replaceVal = self.games[k].get('gameInfo').get('date_object').strftime("%B %d, %Y")
                elif paramParts[2] == 'gameNum':
                    replaceVal = str(self.games[k].get('gameNumber'))
                else: #there are no other supported parameters without multiple parts at this time
                    if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Unsupported parameter",paramParts[3],"found in",thread,type+", ignoring..."
            #apply modifier and replace
            if modifier:
                if modifier.find('%') != -1: #multiple modifiers detected
                    modifiers = modifier.split('%')
                else: modifiers = [modifier]
                for mod in modifiers:
                    if mod=='lower':
                        replaceVal = replaceVal.lower()
                    elif mod=='upper':
                        replaceVal = replaceVal.upper()
                    elif mod=='stripspaces':
                        replaceVal = replaceVal.replace(' ','')
            replaced = replaced.replace(paramParts[3],replaceVal) #replace the param with the replacement value
        replaced = replaced.replace('PLACEHOLDEROPEN','{').replace('PLACEHOLDERCLOSE','}').replace('PLACEHOLDERCOLON',':').replace('PLACEHOLDERMOD','%')
        return replaced

    def generate_title(self,k,thread,timemachine=False,myteamwon=""):
        if thread=="post" or timemachine:
            if myteamwon == "":
                myteamwon = self.didmyteamwin(k)
        if thread == "off": title = self.SETTINGS.get('OFF_THREAD').get('TITLE')
        elif thread == "pre":
            if self.games[k].get('doubleheader') and self.SETTINGS.get('PRE_THREAD').get('CONSOLIDATE_DH'):
                title = self.SETTINGS.get('PRE_THREAD').get('CONSOLIDATED_DH_TITLE')
            else: title = self.SETTINGS.get('PRE_THREAD').get('TITLE')
        elif thread == "game": title = self.SETTINGS.get('GAME_THREAD').get('TITLE')
        elif thread == "post":
            if myteamwon == "0": title = self.SETTINGS.get('POST_THREAD').get('LOSS_TITLE')
            elif myteamwon == "1": title = self.SETTINGS.get('POST_THREAD').get('WIN_TITLE')
            else: title = self.SETTINGS.get('POST_THREAD').get('OTHER_TITLE')

        title = self.replace_params(title,thread,'title',k,timemachine,myteamwon)

        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning",thread,"title:",title,"..."
        return title

    def generate_thread_code(self, thread, gameid, othergameid=None):
        code = ""

        if thread=='pre':
            if othergameid and int(self.games[othergameid].get('gameNumber')) < int(self.games[gameid].get('gameNumber')) and self.SETTINGS.get('PRE_THREAD').get('CONSOLIDATE_DH'):
                tempgameid = othergameid
                othergameid = gameid
                gameid = tempgameid

            gameLive = self.api_download(self.games[gameid].get('link'),True,30)

            if othergameid and self.SETTINGS.get('PRE_THREAD').get('CONSOLIDATE_DH'):
                code += "##Game " + str(self.games[gameid].get('gameNumber')) + "\n"

            ## Temp support for legacy files - required for pitcher reports in generate_probables()
            dir = self.games[gameid].get('url')
            dirs = []
            dirs.append(dir + "gamecenter.xml")
            files = self.download_files(dirs)
            ## Temp support for legacy files^
            if self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('HEADER'): code += "\n\n" + self.generate_header(gameid,thread="pre")
            if self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('BLURB'): code += "\n\n" + self.generate_blurb(gameid,'preview')
            if self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('PROBABLES'): code += "\n\n" + self.generate_probables(files,gameid)
            if self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('FOOTER') and (not othergameid or not self.SETTINGS.get('PRE_THREAD').get('CONSOLIDATE_DH')): code += "\n\n" + self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('FOOTER')
            code += "\n\n"

            if othergameid and self.SETTINGS.get('PRE_THREAD').get('CONSOLIDATE_DH'):
                code += "---\n##Game " + str(self.games[othergameid].get('gameNumber')) + "\n"
                ## Temp support for legacy files - required for pitcher reports in generate_probables()
                odir = self.games[othergameid].get('url')
                odirs = []
                odirs.append(odir + "gamecenter.xml")
                ofiles = self.download_files(odirs)
                ## Temp support for legacy files^
                if self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('HEADER'): code += "\n\n" + self.generate_header(othergameid,thread="pre")
                if self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('BLURB'): code += "\n\n" + self.generate_blurb(othergameid,'preview')
                if self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('PROBABLES'): code += "\n\n" + self.generate_probables(ofiles,othergameid)
                if self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('FOOTER'): code += "\n\n" + self.SETTINGS.get('PRE_THREAD').get('CONTENT').get('FOOTER')
                code += "\n\n"

        elif thread=='game':
            ## Temp support for legacy files
            dir = self.games[gameid].get('url')
            dirs = []
            dirs.append(dir + "gamecenter.xml")
            files = self.download_files(dirs)
            ## Temp support for legacy files^
            if thread == "game":
                if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('HEADER'): code += "\n\n" + self.generate_header(gameid,thread="game")
                if self.games[gameid].get('status').get('abstractGameState') == 'Preview':
                    if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('PREVIEW_BLURB'): code += "\n\n" + self.generate_blurb(gameid,'preview')
                    if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('PREVIEW_PROBABLES'): code += "\n\n" + self.generate_probables(files,gameid)
                if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('BOX_SCORE'): code += "\n\n" + self.generate_boxscore(gameid)
                if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('LINE_SCORE'): code += "\n\n" + self.generate_linescore(gameid)
                if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('SCORING_PLAYS'): code += "\n\n" + self.generate_scoring_plays(gameid)
                if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('HIGHLIGHTS'): code += "\n\n" + self.generate_highlights(gameid,self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('THEATER_LINK'))
                if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('CURRENT_STATE'): code += "\n\n" + self.generate_current_state(gameid)
                code += "\n\n" + self.generate_status(gameid,self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('NEXT_GAME'))
                if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('FOOTER'): code += "\n\n" + self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('FOOTER')

        elif thread=='post':
            if self.SETTINGS.get('POST_THREAD').get('CONTENT').get('HEADER'): code += "\n\n" + self.generate_header(gameid,thread="post")
            if self.SETTINGS.get('POST_THREAD').get('CONTENT').get('BOX_SCORE'): code += "\n\n" + self.generate_boxscore(gameid)
            if self.SETTINGS.get('POST_THREAD').get('CONTENT').get('LINE_SCORE'): code += "\n\n" + self.generate_linescore(gameid)
            if self.SETTINGS.get('POST_THREAD').get('CONTENT').get('SCORING_PLAYS'): code += "\n\n" + self.generate_scoring_plays(gameid)
            if self.SETTINGS.get('POST_THREAD').get('CONTENT').get('HIGHLIGHTS'): code += "\n\n" + self.generate_highlights(gameid,self.SETTINGS.get('POST_THREAD').get('CONTENT').get('THEATER_LINK'))
            code += "\n\n" + self.generate_status(gameid,self.SETTINGS.get('POST_THREAD').get('CONTENT').get('NEXT_GAME'))
            if self.SETTINGS.get('POST_THREAD').get('CONTENT').get('FOOTER'): code += "\n\n" + self.SETTINGS.get('POST_THREAD').get('CONTENT').get('FOOTER')

        code += "\n\n"
        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning all",thread,"thread code..."
        return code

    def generate_probables(self,files,gameid):
        probables = ""
        gameLive = self.api_download(self.games[gameid].get('link'),True,10,apiVer='v1.1')
        awayPitcherData = gameLive.get('liveData').get('boxscore').get('teams').get('away').get('players').get('ID'+str(gameLive.get('gameData').get('probablePitchers').get('away',{}).get('id',0)),{})
        homePitcherData = gameLive.get('liveData').get('boxscore').get('teams').get('home').get('players').get('ID'+str(gameLive.get('gameData').get('probablePitchers').get('home',{}).get('id',0)),{})

        homesub = self.lookup_team_info('sub','name',self.games[gameid].get('gameInfo').get('home').get('team_name'),self.games[gameid].get('gameInfo').get('home').get('sport_code'))
        awaysub = self.lookup_team_info('sub','name',self.games[gameid].get('gameInfo').get('away').get('team_name'),self.games[gameid].get('gameInfo').get('away').get('sport_code'))
        if homesub.find('/') == -1: homeSubLink = self.games[gameid].get('gameInfo').get('home').get('team_name')
        else: homeSubLink = "[" + self.games[gameid].get('gameInfo').get('home').get('team_name') + "](" + homesub + ")"
        if awaysub.find('/') == -1: awaySubLink = self.games[gameid].get('gameInfo').get('away').get('team_name')
        else: awaySubLink = "[" + self.games[gameid].get('gameInfo').get('away').get('team_name') + "](" + awaysub + ")"
        ## Can't find pitcher reports in Stats API, so continuing to use legacy gamecenter.xml for now...
        root = files["gamecenter"].getroot()
        probables_xml = root.find('probables')
        if probables_xml == -1:
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning probables (none)..."
            return ""
        awayReport = probables_xml.find("away/report").text
        if awayReport == None: awayReport = "No report posted."
        homeReport = probables_xml.find("home/report").text
        if homeReport == None: homeReport = "No report posted."

        away_pitcher = awayPitcherData.get('person',{}).get('fullName',"")
        if away_pitcher == "": away_pitcher = "TBA"
        else:
            away_pitcher = "[" + away_pitcher + "](" + "http://mlb.mlb.com/team/player.jsp?player_id=" + str(awayPitcherData.get('person').get('id')) + ")"
            away_pitcher += " (" + str(awayPitcherData.get('seasonStats',{}).get('pitching',{}).get('wins',0)) + "-" + str(awayPitcherData.get('seasonStats',{}).get('pitching',{}).get('losses',0)) + ", " + awayPitcherData.get('seasonStats',{}).get('pitching',{}).get('era','0.00') + " ERA, " +  str(awayPitcherData.get('seasonStats',{}).get('pitching',{}).get('inningsPitched','0')) + " IP)"

        home_pitcher = homePitcherData.get('person',{}).get('fullName',"")
        if home_pitcher == "": home_pitcher = "TBA"
        else:
            home_pitcher = "[" + home_pitcher + "](" + "http://mlb.mlb.com/team/player.jsp?player_id=" + str(homePitcherData.get('person').get('id')) + ")"
            home_pitcher += " (" + str(homePitcherData.get('seasonStats',{}).get('pitching',{}).get('wins',0)) + "-" + str(homePitcherData.get('seasonStats',{}).get('pitching',{}).get('losses',0)) + ", " + homePitcherData.get('seasonStats',{}).get('pitching',{}).get('era','0.00') + " ERA, " +  str(homePitcherData.get('seasonStats',{}).get('pitching',{}).get('inningsPitched','0')) + " IP)"

        probables  = "||Probable Pitcher|Report|\n"
        probables += "|:--|:--|:--|\n"
        probables += "|" + awaySubLink + "|" + away_pitcher + "|" + awayReport + "|\n"
        probables += "|" + homeSubLink + "|" + home_pitcher + "|" + homeReport + "|\n"
        probables += "\n"

        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning probables..."
        return probables

    def generate_blurb(self,gameid,type='preview'):
        gameContent = self.api_download(self.games[gameid].get('content').get('link'),False,5)

        blurb = headline = blurbtext = ""

        homeaway = self.games[gameid].get('homeaway') if self.games[gameid].get('homeaway') else 'mlb'

        headline = gameContent.get('editorial',{}).get(type,{}).get(homeaway,{}).get('headline')
        if not headline and homeaway != 'mlb':
            if self.SETTINGS.get('LOG_LEVEL')>2: print "No",homeaway,"headline available, using mlb headline..."
            headline = gameContent.get('editorial',{}).get(type,{}).get('mlb',{}).get('headline')

        blurbtext = gameContent.get('editorial',{}).get(type,{}).get(homeaway,{}).get('blurb')
        if not blurbtext and homeaway != 'mlb':
            if self.SETTINGS.get('LOG_LEVEL')>2: print "No",homeaway,"blurb available, using mlb headline..."
            blurbtext = gameContent.get('editorial',{}).get(type,{}).get('mlb',{}).get('headline')

        if headline: blurb += "**" + headline + "**"
        if blurbtext: blurb += "\n\n" + blurbtext
        if blurb == "":
            if self.SETTINGS.get('LOG_LEVEL')>2: print "No blurb available, returning empty string..."
        else:
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning",type,"blurb..."
        return blurb

    def download_files(self,dirs): #TODO: Deprecate once Stats API source is found for pitcher reports in `generate_probables()`
        files = dict()

        for dir in dirs:
            try:
                response = urllib2.urlopen(dir)
                if dir[dir.rfind('.'):] == '.json': files[dir[dir.rfind('/')+1:dir.rfind('.')]] = json.load(response)
                elif dir[dir.rfind('.'):] == '.xml': files[dir[dir.rfind('/')+1:dir.rfind('.')]] = ET.parse(response)
            except Exception,e:
                if self.SETTINGS.get('LOG_LEVEL')>2: print "Error downloading " + dir[dir.rfind('.'):] + ":",str(e)
                if dir[dir.rfind('.'):] == '.json': files[dir[dir.rfind('/')+1:dir.rfind('.')]] = {}
                elif dir[dir.rfind('.'):] == '.xml': files[dir[dir.rfind('/')+1:dir.rfind('.')]] = ET.ElementTree("<root>")

        return files

    def generate_header(self,gameid,thread="game"):
        header = ""
        gameLive = self.api_download(self.games[gameid].get('link'),True,10)
        gameContent = self.api_download(self.games[gameid].get('content').get('link'),False,10)

        matchup = "[" + self.games[gameid].get('gameInfo').get('away').get('team_name') + " @ " + self.games[gameid].get('gameInfo').get('home').get('team_name') + "](http://mlb.mlb.com/images/2017_ipad/684/" + self.games[gameid].get('gameInfo').get('away').get('file_code') + self.games[gameid].get('gameInfo').get('home').get('file_code') + "_684.jpg)"

        header += "|" + matchup + " Game Info|Links|\n"
        header += "|:--|:--|\n"
        header += "|**First Pitch:** " + self.games[gameid].get('gameInfo').get('time') + " @ " + gameLive.get('gameData').get('venue').get('name') + "|[Gameday](https://www.mlb.com/gameday/" + str(self.games[gameid].get('gamePk')) + "/)|\n"

        if thread!="pre":
            if len(gameLive.get('gameData').get('weather')) > 0:
                weathertext = "|**Weather:** " + gameLive.get('gameData').get('weather').get('condition') + ", " + gameLive.get('gameData').get('weather').get('temp') + " F, " + "Wind " + gameLive.get('gameData').get('weather').get('wind')
            else: weathertext = "|**Weather:** "
            header += weathertext

            header += "|[Strikezone Map](http://www.brooksbaseball.net/pfxVB/zoneTrack.php?month=" + self.games[gameid].get('gameInfo').get('date_object').strftime(
                "%m") + "&day=" + self.games[gameid].get('gameInfo').get('date_object').strftime("%d") + "&year=" + self.games[gameid].get('gameInfo').get('date_object').strftime(
                "%Y") + "&game=gid_" + gameLive.get('gameData').get('game').get('id').replace('/','_').replace('-','_') + "/)|\n"

        header += "|**TV:** "
        if not gameContent.get('media',{}).get('epg'):
            header += "None"
        else:
            tvData = gameContent.get('media',{}).get('epg',{})[next((i for i,x in enumerate(gameContent.get('media',{}).get('epg',{})) if x.get('title')=='MLBTV'),None)]
            homeTvList = []
            awayTvList = []
            nationalTvList = []
            for x in tvData.get('items',[{}]):
                if x.get('mediaFeedType').upper()=='HOME': homeTvList.append(x.get('callLetters'))
            for x in tvData.get('items',[{}]):
                if x.get('mediaFeedType').upper()=='AWAY': awayTvList.append(x.get('callLetters'))
            for x in tvData.get('items',[{}]):
                if x.get('mediaFeedType').upper()=='NATIONAL': nationalTvList.append(x.get('callLetters'))
            lenAwayTvList = len(awayTvList)
            lenNationalTvList = len(nationalTvList)
            if len(nationalTvList):
                header += "National: " + nationalTvList.pop(0)
                while len(nationalTvList):
                    header += ", " + nationalTvList.pop(0)
            if len(awayTvList):
                if lenNationalTvList>0: header += " // "
                header += self.games[gameid].get('gameInfo').get('away').get('team_name') + ": " + awayTvList.pop(0)
                while len(awayTvList):
                    header += ", " + awayTvList.pop(0)
            if len(homeTvList):
                if lenAwayTvList>0 or (lenAwayTvList==0 and lenNationalTvList>0): header += " // "
                header += self.games[gameid].get('gameInfo').get('home').get('team_name') + ": " + homeTvList.pop(0)
                while len(homeTvList):
                    header += ", " + homeTvList.pop(0)
        if self.games[gameid].get('doubleHeader') != 'N':
            if thread!="pre": header += "|[Game Graph](http://www.fangraphs.com/livewins.aspx?date=" + self.games[gameid].get('gameInfo').get('date_object').strftime("%Y-%m-%d") + "&team=" + self.games[gameid].get('gameInfo').get('home').get('team_name') + "&dh=" + str(self.games[gameid].get('gameNumber')) + "&season=" + self.games[gameid].get('gameInfo').get('date_object').strftime("%Y") + ")|\n"
            else: header += "||\n"
        else:
            if thread!="pre": header += "|[Game Graph](http://www.fangraphs.com/livewins.aspx?date=" + self.games[gameid].get('gameInfo').get('date_object').strftime("%Y-%m-%d") + "&team=" + self.games[gameid].get('gameInfo').get('home').get('team_name') + "&dh=0&season=" + self.games[gameid].get('gameInfo').get('date_object').strftime("%Y") + ")|\n"
            else: header += "||\n"

        header += "|**Radio:** "
        if not gameContent.get('media',{}).get('epg'):
            header += "None"
        else:
            radioData = gameContent.get('media',{}).get('epg',{})[next((i for i,x in enumerate(gameContent.get('media',{}).get('epg',{})) if x.get('title')=='Audio'),None)]
            homeRadioList = []
            awayRadioList = []
            nationalRadioList = []
            for x in radioData.get('items',[{}]):
                if x.get('type').upper()=='HOME': homeRadioList.append(x.get('callLetters'))
            for x in radioData.get('items',[{}]):
                if x.get('type').upper()=='AWAY': awayRadioList.append(x.get('callLetters'))
            for x in radioData.get('items',[{}]):
                if x.get('type').upper()=='NATIONAL': nationalRadioList.append(x.get('callLetters'))
            lenAwayRadioList = len(awayRadioList)
            lenNationalRadioList = len(nationalRadioList)
            if len(nationalRadioList):
                header += "National: " + nationalRadioList.pop(0)
                while len(nationalRadioList):
                    header += ", " + nationalRadioList.pop(0)
            if len(awayRadioList):
                if lenNationalRadioList>0: header += " // "
                header += self.games[gameid].get('gameInfo').get('away').get('team_name') + ": " + awayRadioList.pop(0)
                while len(awayRadioList):
                    header += ", " + awayRadioList.pop(0)
            if len(homeRadioList):
                if lenAwayRadioList>0 or (lenAwayRadioList==0 and lenNationalRadioList>0): header += " // "
                header += self.games[gameid].get('gameInfo').get('home').get('team_name') + ": " + homeRadioList.pop(0)
                while len(homeRadioList):
                    header += ", " + homeRadioList.pop(0)

        header += "|**Notes:** ["+self.games[gameid].get('gameInfo').get('away').get('team_name')+"](http://mlb.mlb.com/mlb/presspass/gamenotes.jsp?c_id=" + self.games[gameid].get('gameInfo').get('away').get('file_code') + "), ["+self.games[gameid].get('gameInfo').get('home').get('team_name')+"](http://mlb.mlb.com/mlb/presspass/gamenotes.jsp?c_id=" + self.games[gameid].get('gameInfo').get('home').get('file_code') + ")|\n"
        if self.games[gameid].get('description',False): header += "|**Game Note:** " + self.games[gameid].get('description') + "||\n"
        header += "\n\n"
        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning header..."
        return header

    def generate_boxscore(self,gameid):
        boxscore = ""
        gameLive = self.api_download(self.games[gameid].get('link'),False,5)
        gameBoxscore = gameLive.get('liveData').get('boxscore')

        awayBattersRand = {}
        awayBatters = []
        for k,v in gameBoxscore.get('teams').get('away').get('players').iteritems():
            if v.get('gameStats',{}).get('batting',{}).get('battingOrder'):
                name = v.get('name').get('boxname')
                pos = v.get('position')
                ab = str(v.get('gameStats').get('batting').get('atBats'))
                r = str(v.get('gameStats').get('batting').get('runs'))
                hits = str(v.get('gameStats').get('batting').get('hits'))
                rbi = str(v.get('gameStats').get('batting').get('rbi'))
                bb = str(v.get('gameStats').get('batting').get('baseOnBalls'))
                so = str(v.get('gameStats').get('batting').get('strikeOuts'))
                ba = str(v.get('seasonStats').get('batting').get('avg'))
                obp = str(v.get('seasonStats').get('batting').get('obp'))
                slg = str(v.get('seasonStats').get('batting').get('slg'))
                id =  str(v.get('id'))
                awayBattersRand.update({v.get('gameStats',{}).get('batting',{}).get('battingOrder') : player.batter(name,pos,ab,r,hits,rbi,bb,so,ba,obp,slg,id)})
        for x in sorted(awayBattersRand):
            awayBatters.append(awayBattersRand[x])

        homeBattersRand = {}
        homeBatters = []
        for k,v in gameBoxscore.get('teams').get('home').get('players').iteritems():
            if v.get('gameStats',{}).get('batting',{}).get('battingOrder'):
                name = v.get('name').get('boxname')
                pos = v.get('position')
                ab = str(v.get('gameStats').get('batting').get('atBats'))
                r = str(v.get('gameStats').get('batting').get('runs'))
                hits = str(v.get('gameStats').get('batting').get('hits'))
                rbi = str(v.get('gameStats').get('batting').get('rbi'))
                bb = str(v.get('gameStats').get('batting').get('baseOnBalls'))
                so = str(v.get('gameStats').get('batting').get('strikeOuts'))
                ba = str(v.get('seasonStats').get('batting').get('avg'))
                obp = str(v.get('seasonStats').get('batting').get('obp'))
                slg = str(v.get('seasonStats').get('batting').get('slg'))
                id =  str(v.get('id'))
                homeBattersRand.update({v.get('gameStats',{}).get('batting',{}).get('battingOrder') : player.batter(name,pos,ab,r,hits,rbi,bb,so,ba,obp,slg,id)})
        for x in sorted(homeBattersRand):
            homeBatters.append(homeBattersRand[x])

        while len(homeBatters) < len(awayBatters):
            homeBatters.append(player.batter())
        while len(awayBatters) < len(homeBatters):
            awayBatters.append(player.batter())

        if len(homeBatters) > 0:
            boxscore += "|" + self.games[gameid].get('gameInfo').get('away').get('team_name') + "|Pos|AB|R|H|RBI|BB|SO|BA/OBP/SLG"
            boxscore += "|" + self.games[gameid].get('gameInfo').get('home').get('team_name') + "|Pos|AB|R|H|RBI|BB|SO|BA/OBP/SLG|"
            boxscore += "\n|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|\n"
            for i in range(0, len(homeBatters)):
                boxscore += "|" + str(awayBatters[i]) + "|" + str(homeBatters[i]) + "|\n"

        if self.SETTINGS.get('GAME_THREAD').get('CONTENT').get('EXTENDED_BOX_SCORE') or (self.SETTINGS.get('POST_THREAD').get('CONTENT').get('EXTENDED_BOX_SCORE') and self.games[gameid].get('final')):
            awayBattingBox = ""
            awayInfoParsed = gameLive.get('liveData').get('boxscore').get('teams').get('away').get('infoParsed')
            if awayInfoParsed:
                ind1 = next((i for i,x in enumerate(awayInfoParsed) if x.get('title').upper() == 'BATTING'), None)
                if ind1 != None: awayBattingInfo = awayInfoParsed[ind1]
                else: awayBattingInfo = None
                if awayBattingInfo:
                    awayBattingFields = awayBattingInfo.get('fields',[{}])
                    for x in awayBattingFields:
                        awayBattingBox += '**' + x.get('label') + '**: ' + x.get('value') + ' '
            homeBattingBox = ""
            homeInfoParsed = gameLive.get('liveData').get('boxscore').get('teams').get('home').get('infoParsed')
            if homeInfoParsed:
                ind2 = next((i for i,x in enumerate(homeInfoParsed) if x.get('title').upper() == 'BATTING'), None)
                if ind2 != None: homeBattingInfo = homeInfoParsed[ind2]
                else: homeBattingInfo = None
                if homeBattingInfo:
                    homeBattingFields = homeBattingInfo.get('fields',[{}])
                    for x in homeBattingFields:
                        homeBattingBox += '**' + x.get('label') + '**: ' + x.get('value') + ' '
            if awayBattingBox != homeBattingBox:
                boxscore += "\n\n|"+self.games[gameid].get('gameInfo').get('away').get('team_name')+"|"+self.games[gameid].get('gameInfo').get('home').get('team_name')+"|\n"
                boxscore += "|:--|:--|\n"
                boxscore += "|" + awayBattingBox + "|" + homeBattingBox + "|\n"

        awayPitchers = []
        awayPitcherIds = gameBoxscore.get('teams').get('away').get('pitchers')
        for i in awayPitcherIds:
            v = gameBoxscore.get('teams').get('away').get('players').get('ID'+str(i))
            name = v.get('name').get('boxname')
            ip = str(v.get('gameStats').get('pitching').get('inningsPitched'))
            h = str(v.get('gameStats').get('pitching').get('hits'))
            r = str(v.get('gameStats').get('pitching').get('runs'))
            er = str(v.get('gameStats').get('pitching').get('earnedRuns'))
            bb = str(v.get('gameStats').get('pitching').get('baseOnBalls'))
            so = str(v.get('gameStats').get('pitching').get('strikeOuts'))
            p = str(v.get('gameStats').get('pitching').get('pitchesThrown'))
            s = str(v.get('gameStats').get('pitching').get('strikes'))
            era = str(v.get('seasonStats').get('pitching').get('era'))
            id = str(i)
            awayPitchers.append(player.pitcher(name,ip,h,r,er,bb,so,p,s,era,id))

        homePitchers = []
        homePitcherIds = gameBoxscore.get('teams').get('home').get('pitchers')
        for i in homePitcherIds:
            v = gameBoxscore.get('teams').get('home').get('players').get('ID'+str(i))
            name = v.get('name').get('boxname')
            ip = str(v.get('gameStats').get('pitching').get('inningsPitched'))
            h = str(v.get('gameStats').get('pitching').get('hits'))
            r = str(v.get('gameStats').get('pitching').get('runs'))
            er = str(v.get('gameStats').get('pitching').get('earnedRuns'))
            bb = str(v.get('gameStats').get('pitching').get('baseOnBalls'))
            so = str(v.get('gameStats').get('pitching').get('strikeOuts'))
            p = str(v.get('gameStats').get('pitching').get('pitchesThrown'))
            s = str(v.get('gameStats').get('pitching').get('strikes'))
            era = str(v.get('seasonStats').get('pitching').get('era'))
            id = str(i)
            homePitchers.append(player.pitcher(name,ip,h,r,er,bb,so,p,s,era,id))

        while len(homePitchers) < len(awayPitchers):
            homePitchers.append(player.pitcher())
        while len(awayPitchers) < len(homePitchers):
            awayPitchers.append(player.pitcher())

        if len(homePitchers) > 0:
            boxscore += "\n\n"
            boxscore += "|" + self.games[gameid].get('gameInfo').get('away').get('team_name') + "|IP|H|R|ER|BB|SO|P-S|ERA|"
            boxscore += self.games[gameid].get('gameInfo').get('home').get('team_name') + "|IP|H|R|ER|BB|SO|P-S|ERA|\n"
            boxscore += "|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|\n"
            for i in range(0, len(homePitchers)):
                boxscore += "|" + str(awayPitchers[i]) + "|" + str(homePitchers[i]) + "|\n"

        if boxscore == "":
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning boxscore (none)..."
        else:
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning boxscore..."
        return boxscore

    def generate_linescore(self,gameid):
        linescore = ""
        if self.games[gameid].get('status').get('abstractGameState') == 'Preview':
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning linescore (none)..."
            return linescore
        gameLive = self.api_download(self.games[gameid].get('link'),False,5)
        gameLinescore  = gameLive.get('liveData').get('linescore')
        innings = gameLinescore.get('innings')
        numInnings = len(innings) if len(innings) > 9 else 9
        homesub = self.lookup_team_info('sub','name',self.games[gameid].get('gameInfo').get('home').get('team_name'),self.games[gameid].get('gameInfo').get('home').get('sport_code'))
        awaysub = self.lookup_team_info('sub','name',self.games[gameid].get('gameInfo').get('away').get('team_name'),self.games[gameid].get('gameInfo').get('away').get('sport_code'))
        if homesub.find('/') == -1: homeSubLink = self.games[gameid].get('gameInfo').get('home').get('team_name')
        else: homeSubLink = "[" + self.games[gameid].get('gameInfo').get('home').get('team_name') + "](" + homesub + ")"
        if awaysub.find('/') == -1: awaySubLink = self.games[gameid].get('gameInfo').get('away').get('team_name')
        else: awaySubLink = "[" + self.games[gameid].get('gameInfo').get('away').get('team_name') + "](" + awaysub + ")"
        linescore = "Linescore|"
        for i in range(1,numInnings+1):
            linescore += str(i) + "|"
        linescore += "|R|H|E|LOB\n"
        linescore += ":--"
        for i in range(1,numInnings + 6):
            linescore += "|:--"
        linescore += "\n" + awaySubLink + "|"
        x=1
        for v in innings:
            if type(v.get('away')) is dict:
                linescore += str(v.get('away').get('runs','')) + "|"
            else:
                linescore += str(v.get('away','')) + "|"
            x+=1
        if x < numInnings+1:
            for i in range(x, numInnings+1):
                linescore += "|"
        awayLob = None
        awayInfoParsed = gameLive.get('liveData').get('boxscore').get('teams').get('away').get('infoParsed')
        if awayInfoParsed:
            ind1 = next((i for i,x in enumerate(awayInfoParsed) if x.get('title').upper() == 'BATTING'), None)
            if ind1 != None: awayBattingInfo = awayInfoParsed[ind1]
            else: awayBattingInfo = None
            if awayBattingInfo:
                awayBattingFields = awayBattingInfo.get('fields',{})
                ind2 = next((i for i,x in enumerate(awayBattingFields) if x.get('label').lower() == 'team lob'), None)
                if ind2 != None: awayLobDict = awayBattingFields[ind2]
                else: awayLobDict = None
                if awayLobDict: awayLob = awayLobDict.get('value').replace('.','')
        if not awayLob: awayLob = '0'
        if gameLinescore.get('teams',{}).get('away',{}).get('runs'):
            linescore += "|" + str(gameLinescore.get('teams').get('away').get('runs',0)) + "|" + str(gameLinescore.get('teams').get('away').get('hits',0)) + "|" + str(gameLinescore.get('teams').get('away').get('errors',0)) + "|" + awayLob
        else:
            linescore += "|" + str(gameLinescore.get('away',{}).get('runs',0)) + "|" + str(gameLinescore.get('away',{}).get('hits',0)) + "|" + str(gameLinescore.get('away',{}).get('errors',0)) + "|" + awayLob
        linescore += "\n" + homeSubLink + "|"
        x=1
        for v in innings:
            if type(v.get('home')) is dict:
                linescore += str(v.get('home').get('runs','')) + "|"
            else:
                linescore += str(v.get('home','')) + "|"
            x+=1
        if x < numInnings+1:
            for i in range(x, numInnings+1):
                linescore += "|"
        homeLob = None
        homeInfoParsed = gameLive.get('liveData').get('boxscore').get('teams').get('home').get('infoParsed')
        if homeInfoParsed:
            ind3 = next((i for i,x in enumerate(homeInfoParsed) if x.get('title').upper() == 'BATTING'), None)
            if ind3 != None: homeBattingInfo = homeInfoParsed[ind3]
            else: homeBattingInfo = None
            if homeBattingInfo:
                homeBattingFields = homeBattingInfo.get('fields',{})
                ind4 = next((i for i,x in enumerate(homeBattingFields) if x.get('label').lower() == 'team lob'), None)
                if ind4 != None: homeLobDict = homeBattingFields[ind4]
                else: homeLobDict = None
                if homeLobDict: homeLob = homeLobDict.get('value').replace('.','')
        if not homeLob: homeLob = '0'
        if gameLinescore.get('teams',{}).get('home',{}).get('runs'):
            linescore += "|" + str(gameLinescore.get('teams').get('home').get('runs',0)) + "|" + str(gameLinescore.get('teams').get('home').get('hits',0)) + "|" + str(gameLinescore.get('teams').get('home').get('errors',0)) + "|" + homeLob
        else:
            linescore += "|" + str(gameLinescore.get('home',{}).get('runs',0)) + "|" + str(gameLinescore.get('home',{}).get('hits',0)) + "|" + str(gameLinescore.get('home',{}).get('errors',0)) + "|" + homeLob
        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning linescore..."
        return linescore + "\n"

    def generate_scoring_plays(self,gameid):
        scoringplays = ""
        gameLive = self.api_download(self.games[gameid].get('link'),False,5)
        gameScoringPlays = gameLive.get('liveData').get('plays').get('scoringPlays')
        if len(gameScoringPlays) == 0:
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning scoringplays (none)..."
            return scoringplays
        gameAllPlays = gameLive.get('liveData').get('plays').get('allPlays')
        plays = []
        for i in gameScoringPlays:
            plays.append(next((v for v in gameAllPlays if v.get('about').get('atBatIndex')==i),None))
        scoringplays += "Inning|Scoring Play Description|Score\n"
        scoringplays += ":--|:--|:--\n"
        prevInn = ""
        for play in plays:
            thisInn = "Bottom " + play.get('about').get('inning') if play.get('about').get('halfInning')=='bottom' else "Top " + play.get('about').get('inning')
            if thisInn != prevInn: scoringplays += thisInn + "|"
            else: scoringplays += "| |"
            prevInn = thisInn
            scoringplays += play.get('result').get('description') + "|"
            homeScore = play.get('result').get('homeScore',0)
            awayScore = play.get('result').get('awayScore',0)
            if int(homeScore) > int(awayScore): leader = 'home'
            elif int(homeScore) < int(awayScore): leader = 'away'
            else: leader = ""
            if leader != "":
                if int(homeScore) > int(awayScore): scoringplays += str(homeScore) + "-" + str(awayScore)
                else: scoringplays += str(awayScore) + "-" + str(homeScore)
                scoringplays += " " + self.games[gameid].get('gameInfo').get(leader).get('name_abbrev').upper() + "\n"
            else: scoringplays += str(homeScore) + "-" + str(awayScore) + "\n"
        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning scoringplays..."
        return scoringplays

    def generate_highlights(self,gameid,theater_link=False):
        highlights = ""
        gameContent = self.api_download(self.games[gameid].get('content').get('link'),False,5)
        gameItems = (v for v in gameContent.get('highlights',{}).get('live',{}).get('items',{}) if v.get('type')=='video')
        highlights += "|Team|Highlight|Links|\n"
        highlights += "|:--|:--|:--|\n"
        unorderedHighlights = {}
        for x in gameItems:
            unorderedHighlights.update({x.get('id') : x})
        if len(unorderedHighlights) == 0:
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning highlights (none)..."
            return ""
        sortedHighlights = []
        for x in sorted(unorderedHighlights):
            sortedHighlights.append(unorderedHighlights[x])
        for x in sortedHighlights:
            team = next((v.get('value') for v in x.get('keywordsDisplay') if v.get('type')=='team_id'),None)
            if not team: subLink='[](/MLB)'
            else: subLink = self.lookup_team_info('sublink','team_id',team)
            sdLink = next((v.get('url') for v in x.get('playbacks') if v.get('name')=='FLASH_1200K_640X360'),None)
            if not sdLink: sdLink = ""
            else: sdLink = "[SD]("+sdLink+")"
            hdLink = next((v.get('url') for v in x.get('playbacks') if v.get('name')=='FLASH_2500K_1280X720'),None)
            if not hdLink: hdLink = ""
            else: hdLink = "[HD]("+hdLink+")"
            highlights += "|" + subLink + "|" + x.get('headline') + " (" + x.get('duration') + ")|" + sdLink + " " + hdLink + "|\n"
        if theater_link:
            gamedate = self.games[gameid].get('gameInfo').get('date_object').strftime('%Y%m%d')
            game_pk = self.games[gameid].get('gamePk')
            highlights += "||See all highlights at [Baseball.Theater](http://baseball.theater/game/" + gamedate + "/" + str(game_pk) + ")||\n"
        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning highlights..."
        return highlights

    def generate_current_state(self,gameid):
        current_state = ""

        gameLive = self.api_download(self.games[gameid].get('link'),False,5)

        detailedState = self.games[gameid].get('status').get('detailedState')
        abstractGameState = self.games[gameid].get('status').get('abstractGameState')
        if abstractGameState == 'Live' and detailedState == 'In Progress':
            current_state += gameLive.get('liveData').get('linescore').get('inningHalf') + " of the " + gameLive.get('liveData').get('linescore').get('currentInningOrdinal')

            currentPlay = gameLive.get('liveData').get('plays').get('currentPlay')
            offense = gameLive.get('liveData').get('players').get('offense')
            defense = gameLive.get('liveData').get('players').get('defense')
            outs = str(currentPlay.get('count').get('outs','0'))
            if outs == '3':
                if gameLive.get('liveData').get('linescore').get('inningHalf') == 'Top': current_state = current_state.replace('Top','Middle')
                elif gameLive.get('liveData').get('linescore').get('inningHalf') == 'Bottom': current_state = current_state.replace('Bottom','End')
                if current_state == 'Middle of the 7th': current_state = "Seventh inning stretch"

                dueup = self.lookup_player_info(offense.get('batter'),'fullName')
                comingup = " with " + dueup

                ondeck = self.lookup_player_info(offense.get('onDeck'),'fullName')
                comingup += ", " + ondeck

                inhole = self.lookup_player_info(offense.get('inHole'),'fullName')
                comingup += ", and " + inhole

                teamcomingup = self.lookup_team_info('name','team_id',offense.get('teamID'))
                comingup += " due up for the " + teamcomingup + "."

                if comingup == " with , , and  due up for the " + teamcomingup + ".": comingup = "with the " + teamcomingup + " coming up to bat."
                current_state += comingup
            else:
                if not offense.get('first') and not offense.get('second') and not offense.get('third'): runners = "bases empty"
                elif offense.get('first') and not offense.get('second') and not offense.get('third'): runners = "runner on first"
                elif not offense.get('first') and offense.get('second') and not offense.get('third'): runners = "runner on second"
                elif not offense.get('first') and not offense.get('second') and offense.get('third'): runners = "runner on third"
                elif offense.get('first') and offense.get('second') and not offense.get('third'): runners = "runners on first and second"
                elif offense.get('first') and not offense.get('second') and offense.get('third'): runners = "runners on first and third"
                elif not offense.get('first') and offense.get('second') and offense.get('third'): runners = "runners on second and third"
                elif offense.get('first') and offense.get('second') and offense.get('third'): runners = "bases loaded"

                current_state += ", " + runners

                outtext = " out" if outs=='1' else " outs"
                current_state += ", " + outs + outtext

                count = str(currentPlay.get('count').get('balls','0')) + "-" + str(currentPlay.get('count').get('strikes','0'))
                current_state += ", and a count of " + count

                atbat = self.lookup_player_info(currentPlay.get('matchup').get('batter'),'fullName')
                if not atbat: atbat = "*Unknown*"
                current_state += " with " + atbat + " batting"

                onthemound = self.lookup_player_info(currentPlay.get('matchup').get('pitcher'),'fullName')
                if not onthemound: onthemound = "*Unknown*"
                current_state += " and " + onthemound + " pitching."

                ondeck = self.lookup_player_info(offense.get('onDeck'),'fullName')
                inthehole = self.lookup_player_info(offense.get('inHole'),'fullName')
                if ondeck:
                    current_state += " " + ondeck + " is on deck"
                    if inthehole: current_state += ", and " + inthehole + " is in the hole."    
        elif detailedState.startswith('Delayed') or detailedState.startswith('Suspended'):
            if self.games[gameid].get('status').get('reason'):
                if detailedState.find(self.games[gameid].get('status').get('reason')) != -1:
                    current_state += "###Game Status: " + detailedState
                else:
                    current_state += "###Game Status: " + detailedState + " due to " + self.games[gameid].get('status').get('reason')
            else:
                current_state += "###Game Status: " + detailedState + " due to unspecified reason"
        elif detailedState.startswith('Warmup') or detailedState.lower().startswith('manager challenge') or detailedState.lower().startswith('instant replay') or detailedState.lower().startswith('umpire review'):
            if self.games[gameid].get('status').get('reason'):
                if detailedState.find(self.games[gameid].get('status').get('reason')) != -1:
                    current_state += "###Game Status: " + detailedState
                else:
                    current_state += "###Game Status: " + detailedState + ": " + self.games[gameid].get('status').get('reason')
            else:
                current_state += "###Game Status: " + detailedState
        else:                
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning current_state (none)..."
            return current_state

        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning current_state..."
        return current_state

    def generate_decisions(self,gameid):
        decisions = ""
        gameLive = self.api_download(self.games[gameid].get('link'),False,5,False)
        homeRuns = gameLive.get('liveData').get('linescore').get('home').get('runs')
        awayRuns = gameLive.get('liveData').get('linescore').get('away').get('runs')
        homeName = gameLive.get('gameData').get('teams').get('home').get('name').get('brief')
        awayName = gameLive.get('gameData').get('teams').get('away').get('name').get('brief')
        homeSubLink = self.lookup_team_info('sublink','team_id',str(self.games[gameid].get('gameInfo').get('home').get('team_id')),self.games[gameid].get('gameInfo').get('home').get('sport_code'))
        awaySubLink = self.lookup_team_info('sublink','team_id',str(self.games[gameid].get('gameInfo').get('away').get('team_id')),self.games[gameid].get('gameInfo').get('away').get('sport_code'))
        winner = ""

        if int(homeRuns) > int(awayRuns): winner = "home"
        elif int(awayRuns) > int(homeRuns): winner = "away"
        elif int(homeRuns) == int(awayRuns): 
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning decisions (none, tie)..."
            return decisions

        loser = "away" if winner=="home" else "home"
        winningPitcher = gameLive.get('liveData').get('boxscore').get('teams').get(winner).get('players').get('ID'+str(gameLive.get('liveData').get('linescore').get('pitchers').get('win')))
        losingPitcher = gameLive.get('liveData').get('boxscore').get('teams').get(loser).get('players').get('ID'+str(gameLive.get('liveData').get('linescore').get('pitchers').get('loss')))
        savePitcher = None
        savePitcher = gameLive.get('liveData').get('boxscore').get('teams').get(winner).get('players').get('ID'+str(gameLive.get('liveData').get('linescore').get('pitchers').get('save')))
        decisions += "|Decisions||" + "\n"
        decisions += "|:--|:--|" + "\n"
        decisions += "|" + awaySubLink + "|"
        if winner=='away':
            if winningPitcher: decisions += "[" + winningPitcher.get('name').get('boxname') + "](http://mlb.mlb.com/team/player.jsp?player_id=" + str(winningPitcher.get('id')) + ") " + winningPitcher.get('gameStats').get('pitching').get('note')
            else: decisions += "Winning pitcher data not available"
            if savePitcher: decisions += ", [" + savePitcher.get('name').get('boxname') + "](http://mlb.mlb.com/team/player.jsp?player_id=" + str(savePitcher.get('id')) + ") " + savePitcher.get('gameStats').get('pitching').get('note') + "|\n"
            else: decisions += "|\n"
        else:
            if losingPitcher: decisions += "[" + losingPitcher.get('name').get('boxname') + "](http://mlb.mlb.com/team/player.jsp?player_id=" + str(losingPitcher.get('id')) + ") " + losingPitcher.get('gameStats').get('pitching').get('note') + "|\n"
            else: decisions += "Losing pitcher data not available|\n"

        decisions += "|" + homeSubLink + "|"
        if winner=='home':
            if winningPitcher: decisions += "[" + winningPitcher.get('name').get('boxname') + "](http://mlb.mlb.com/team/player.jsp?player_id=" + str(winningPitcher.get('id')) + ") " + winningPitcher.get('gameStats').get('pitching').get('note')
            else: decisions += "Winning pitcher data not available"
            if savePitcher: decisions += ", [" + savePitcher.get('name').get('boxname') + "](http://mlb.mlb.com/team/player.jsp?player_id=" + str(savePitcher.get('id')) + ") " + savePitcher.get('gameStats').get('pitching').get('note') + "|\n"
            else: decisions += "|\n"
        else:
            if losingPitcher: decisions += "[" + losingPitcher.get('name').get('boxname') + "](http://mlb.mlb.com/team/player.jsp?player_id=" + str(losingPitcher.get('id')) + ") " + losingPitcher.get('gameStats').get('pitching').get('note') + "|\n"
            else: decisions += "Losing pitcher data not available|\n"

        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning decisions..."
        return decisions

    def get_status(self,gameid):
        sched = self.api_download('/api/v1/schedule?language=en&gamePk=' + str(self.games[gameid].get('gamePk')),localWait=2)
        if len(sched.get('dates'))>1:
            todaygames = sched.get('dates')[next((i for i,x in enumerate(sched.get('dates')) if x.get('date') == self.games[gameid].get('gameInfo').get('date_object').strftime('%Y-%m-%d')), None)].get('games')
            thisgame = next((x for i,x in enumerate(todaygames) if x.get('gamePk') == self.games[gameid].get('gamePk')), None)
            if self.SETTINGS.get('LOG_LEVEL')>3: print "Got status:",thisgame.get('status').get('abstractGameState'),"/",thisgame.get('status').get('detailedState')
            return thisgame.get('status')
        else:
            if self.SETTINGS.get('LOG_LEVEL')>3: print "Got status:",sched.get('dates')[0].get('games')[0].get('status').get('abstractGameState'),"/",sched.get('dates')[0].get('games')[0].get('status').get('detailedState')
            return sched.get('dates')[0].get('games')[0].get('status')

    def get_gameDate(self,gamePk,d=datetime.today().date()):
        sched = self.api_download('/api/v1/schedule?language=en&gamePk=' + str(gamePk),localWait=2)
        if len(sched.get('dates'))>1:
            todaygames = sched.get('dates')[next((i for i,x in enumerate(sched.get('dates')) if x.get('date') == d.strftime('%Y-%m-%d')), None)].get('games')
            thisgame = next((x for i,x in enumerate(todaygames) if str(x.get('gamePk')) == str(gamePk)), None)
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Got gameDate:",thisgame.get('gameDate')
            return thisgame.get('gameDate')
        else:
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Got gameDate:",sched.get('dates')[0].get('games')[0].get('gameDate')
            return sched.get('dates')[0].get('games')[0].get('gameDate')

    def generate_status(self,k,include_next_game=False):
        status = ""
        gamelive = self.api_download(self.games[k].get('link'))
        detailedState = self.games[k].get('status').get('detailedState')
        abstractGameState = self.games[k].get('status').get('abstractGameState')
        reason = self.games[k].get('status').get('reason')
        if self.SETTINGS.get('LOG_LEVEL')>2: print "Status:",abstractGameState,"/",detailedState
        homeRuns = gamelive.get('liveData').get('linescore').get('home',{}).get('runs',0)
        awayRuns = gamelive.get('liveData').get('linescore').get('away',{}).get('runs',0)
        homeName = self.games[k].get('gameInfo').get('home').get('team_name')
        awayName = self.games[k].get('gameInfo').get('away').get('team_name')
        if abstractGameState == "Final" and not detailedState.startswith('Cancelled') and not detailedState.startswith('Postponed'):
            status += "##" + detailedState.replace('Game Over','Final')
            if int(homeRuns) < int(awayRuns):
                status += ": " + awayRuns + "-" + homeRuns + " " + awayName + "\n"
                status += self.generate_decisions(k)
                if include_next_game: status += "\n" + self.generate_next_game(thisPk=self.games[k].get('gamePk')) + "\n\n"
                if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning status (Final/Away Win)..."
                return status
            elif int(homeRuns) > int(awayRuns):
                status += ": " + homeRuns + "-" + awayRuns + " " + homeName + "\n"
                status += self.generate_decisions(k)
                if include_next_game: status += "\n" + self.generate_next_game(thisPk=self.games[k].get('gamePk')) + "\n\n"
                if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning status (Final/Home Win)..."
                return status
            elif int(homeRuns) == int(awayRuns):
                if include_next_game: status += "\n\n" + self.generate_next_game(thisPk=self.games[k].get('gamePk')) + "\n\n"
                if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning status (Final/Tie)..."
                return status
        elif detailedState.startswith("Postponed") or detailedState.startswith("Suspended") or detailedState.startswith("Cancelled"):
            if reason:
                if detailedState.find(reason) != -1:
                    status += "##Game Status: " + detailedState + "\n\n"
                else:
                    status += "##Game Status: " + detailedState + " due to " + reason + "\n\n"
            else:
                status += "##Game Status: " + detailedState + "\n\n"
            if include_next_game: status += self.generate_next_game(thisPk=self.games[k].get('gamePk')) + "\n\n"
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning status (Postponed, Suspended, or Cancelled)..."
            return status
        else:
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning status (none)..."
            return status

    def generate_next_game(self,next_game=None,team_id="",thisPk=0):
        next = ""
        if not next_game: next_game = self.next_game(7,thisPk,team_id)
        if next_game.get('date'):
            if next_game.get('event_time') == '3:33 AM': next_game.update({'event_time' : 'Time TBD'})
            next += "**Next Game:** " + next_game.get('date').strftime("%A, %B %d") + ", " + next_game.get('event_time')
            if next_game.get('homeaway') == 'away':
                next += " @ " + next_game.get('home_team_name')
            else:
                next += " vs " + next_game.get('away_team_name')
            if next_game.get('series') and next_game.get('series_num') and next_game.get('gameType') != 'R':
                next += " (" + next_game.get('series') 
                if next_game.get('series_num') != '0' and next_game.get('gameType') not in ['I', 'E', 'S','R']:
                    next += " Game " + next_game.get('series_num')
                next += ")"
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning next game..."
            return next
        if self.SETTINGS.get('LOG_LEVEL')>2: print "Next game not found, returning empty string..."
        return next

    def didmyteamwin(self, k):
    #returns 0 for loss, 1 for win, 2 for tie, 3 for postponed/suspended/canceled, blank for exception
        myteamwon = ""
        hometeam = self.games[k].get('teams',{}).get('home',{}).get('team',{}).get('id')
        awayteam = self.games[k].get('teams',{}).get('away',{}).get('team',{}).get('id')
        if self.games[k].get('homeaway') not in ["home","away"]:
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Cannot determine if my team is home or away, returning empty string for whether my team won..."
            return myteamwon
        if self.games[k].get('status').get('abstractGameState') == "Final" and not self.games[k].get('status').get('detailedState').startswith("Postponed") and not self.games[k].get('status').get('detailedState').startswith("Cancelled"):
            gameLive = self.api_download(self.games[k].get('link'))
            hometeamruns = int(gameLive.get('liveData').get('linescore',{}).get('home',{}).get('runs',0))
            awayteamruns = int(gameLive.get('liveData').get('linescore',{}).get('away',{}).get('runs',0))
            if hometeamruns == awayteamruns:
                myteamwon = "2"
                if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning whether my team won (2-TIE)..."
                return myteamwon
            else:
                if hometeamruns < awayteamruns:
                    if self.games[k].get('homeaway') == "home":
                        myteamwon = "0"
                    elif self.games[k].get('homeaway') == "away":
                        myteamwon = "1"
                    if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning whether my team won ("+myteamwon+")..."
                    return myteamwon
                elif hometeamruns > awayteamruns:
                    if self.games[k].get('homeaway') == "home":
                        myteamwon = "1"
                    elif self.games[k].get('homeaway') == "away":
                        myteamwon = "0"
                    if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning whether my team won ("+myteamwon+")..."
                    return myteamwon
        elif self.games[k].get('status').get('detailedState').startswith("Postponed") or self.games[k].get('status').get('detailedState').startswith("Suspended") or self.games[k].get('status').get('detailedState').startswith("Cancelled"):
            myteamwon = "3"
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning whether my team won: (3-postponed, suspended, or canceled)..."
            return myteamwon
        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning whether my team won: (exception)..." + myteamwon
        return myteamwon

    def next_game(self,check_days=14,thisPk=0,team_id=""):
        if not(team_id): team_id = self.lookup_team_info('team_id','team_code',self.SETTINGS.get('TEAM_CODE'))
        if self.SETTINGS.get('LOG_LEVEL')>2: print datetime.strftime(datetime.today(), "%d %I:%M:%S %p"),"Searching for next game..."
        if thisPk==None: thisPk=0
        today = datetime.today().date()
        #today = datetime.strptime('2018-04-06','%Y-%m-%d').date() # leave commented unless testing
        for d in (today + timedelta(days=x) for x in range(0, check_days)):
            next_game = {}
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Searching for games on",d
            daygames = self.get_schedule(d,team_id)

            i=0
            if not daygames[0]:
                if self.SETTINGS.get('LOG_LEVEL')>2: print "No games found on",d
                continue

            for daygame in daygames:
                hometeam = daygame.get('teams',{}).get('home',{}).get('team',{}).get('id')
                awayteam = daygame.get('teams',{}).get('away',{}).get('team',{}).get('id')
                homeaway = None
                if str(hometeam) == str(team_id):
                    homeaway = 'home'
                elif str(awayteam) == str(team_id):
                    homeaway = 'away'
                if homeaway != None:
                    if str(daygame.get('gamePk')) == str(thisPk) and d==today:
                        if self.SETTINGS.get('LOG_LEVEL')>2: print "Skipping current game on",d
                    elif daygame.get('doubleHeader') in ['Y','S']:
                        #make sure not to return DH game 1 if current game is DH game 2
                        thisgame = self.get_teams_time(pk=thisPk,d=d)
                        gameinfo = self.get_teams_time(pk=daygame.get('gamePk'),d=d)
                        if thisgame.get('date_object') > gameinfo.get('date_object'): continue
                        else:
                            next_game[i] = {'pk': daygame.get('gamePk'), 'date' : d, 'days_away' : (d - today).days, 'homeaway' : homeaway, 'home_code' : gameinfo.get('home').get('team_code'), 'away_code' : gameinfo.get('away').get('team_code'), 'home_team_name' : gameinfo.get('home').get('team_name'), 'away_team_name' : gameinfo.get('away').get('team_name'), 'event_time' : gameinfo.get('date_object').strftime("%I:%M %p %Z"), 'series' : daygame.get('seriesDescription'), 'series_num' : daygame.get('seriesGameNumber'), 'gameType' : daygame.get('gameType')}
                            i += 1
                    else:
                        gameinfo = self.get_teams_time(pk=daygame.get('gamePk'),d=d)
                        next_game[i] = {'pk': daygame.get('gamePk'), 'date' : d, 'days_away' : (d - today).days, 'homeaway' : homeaway, 'home_code' : gameinfo.get('home').get('team_code'), 'away_code' : gameinfo.get('away').get('team_code'), 'home_team_name' : gameinfo.get('home').get('team_name'), 'away_team_name' : gameinfo.get('away').get('team_name'), 'event_time' : gameinfo.get('date_object').strftime("%I:%M %p %Z"), 'series' : daygame.get('seriesDescription'), 'series_num' : daygame.get('seriesGameNumber'), 'gameType' : daygame.get('gameType')}
                        i += 1

            if len(next_game): 
                if self.SETTINGS.get('LOG_LEVEL')>2: print "next_game found game(s):",next_game
            if len(next_game)>1:
                for ngk,ng in next_game.items():
                    if (ng.get('homeaway')=='home' and self.lookup_team_info(field='team_code',lookupfield='team_code',lookupval=ng.get('away_code'))==None) or (ng.get('homeaway')=='away' and self.lookup_team_info(field='team_code',lookupfield='team_code',lookupval=ng.get('home_code'))==None):
                        if self.SETTINGS.get('LOG_LEVEL')>2: print "Found game with placeholder opponent, skipping " + ng.get('pk') + "..."
                    else:
                        if self.SETTINGS.get('LOG_LEVEL')>2: print datetime.strftime(datetime.today(), "%d %I:%M:%S %p"),"Found next game ("+str(ng.get('pk'))+")",(d - today).days,"day(s) away on",d.strftime('%m/%d/%Y') + "..."
                        return ng
                else:
                    if self.SETTINGS.get('LOG_LEVEL')>2: print "Next game lookup found only games with placeholder opponents, returning the first one..."
                    return next_game[0]
            elif len(next_game)==1:
                if self.SETTINGS.get('LOG_LEVEL')>2: print datetime.strftime(datetime.today(), "%d %I:%M:%S %p"),"Found next game",(d - today).days,"day(s) away on",d.strftime('%m/%d/%Y') + "..."
                return next_game[0]
        if self.SETTINGS.get('LOG_LEVEL')>2: print datetime.strftime(datetime.today(), "%d %I:%M:%S %p"),"Found no games in next",check_days,"days..."
        return {}

    def last_game(self,check_days, team_id=""):
        if self.SETTINGS.get('LOG_LEVEL')>2: print datetime.strftime(datetime.today(), "%d %I:%M:%S %p"),"Searching for last game..."
        last_game = {}
        today = datetime.today().date()
        #today = datetime.strptime('2018-04-06','%Y-%m-%d').date() # leave commented unless testing
        for d in (today - timedelta(days=x) for x in range(1, check_days)):
            if self.SETTINGS.get('LOG_LEVEL')>2: print "Searching for games on",d
            daygames = self.get_schedule(d,team_id)
            if not daygames[0]:
                if self.SETTINGS.get('LOG_LEVEL')>2: print "No games found on",d
            else:
                if self.SETTINGS.get('LOG_LEVEL')>2: print "last_game found game(s):",daygames
                last_game.update({'date' : d, 'days_ago' : (today-d).days, 'pk' : daygames[0].get('gamePk')})
                return last_game
        if self.SETTINGS.get('LOG_LEVEL')>2: print datetime.strftime(datetime.today(), "%d %I:%M:%S %p"),"Found no games in last",check_days,"days..."
        return last_game

    def lookup_team_info(self, field="name_abbrev", lookupfield="team_code", lookupval=None, sport_code="mlb"):
        if sport_code==None: sport_code='mlb'
        if not self.TEAMINFO.get(sport_code):
            try:
                if self.SETTINGS.get('LOG_LEVEL')>3: print "Downloading team info from MLB: http://mlb.com/lookup/json/named.team_all.bam?sport_code=%27" + sport_code + "%27&active_sw=%27Y%27&all_star_sw=%27N%27"
                response = urllib2.urlopen("http://mlb.com/lookup/json/named.team_all.bam?sport_code=%27" + sport_code + "%27&active_sw=%27Y%27&all_star_sw=%27N%27")
                self.TEAMINFO.update({sport_code : json.load(response)})
            except urllib2.URLError, e:
                if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Couldn't connect to MLB server to download team info, returning None:",e
                return -1
            except urllib2.HTTPError, e:
                if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Couldn't download team info, returning None:",e
                return -1
            except Exception as e:
                if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Unknown error downloading team info, returning None:",e
                return -1
        else:
            if self.SETTINGS.get('LOG_LEVEL')>3: print 'Using cached team info for sport code ' + sport_code + '...'

        teamlist = self.TEAMINFO.get(sport_code).get('team_all').get('queryResults').get('row')
        for team in teamlist:
            if team.get(lookupfield,"").lower() == lookupval.lower():
                if field=="all":
                   return team
                elif sport_code != 'mlb' and field in ["sub","sublink"]:
                    return team.get('name_abbrev') #no support for these fields for non-MLB teams, returning what we do have
                elif field in ["sub","sublink"]:
                    team_id = team.get('team_id')
                    subs = {
                        "142": "/r/minnesotatwins",
                        "145": "/r/WhiteSox",
                        "116": "/r/MotorCityKitties",
                        "118": "/r/KCRoyals",
                        "114": "/r/WahoosTipi",
                        "140": "/r/TexasRangers",
                        "117": "/r/Astros",
                        "133": "/r/OaklandAthletics",
                        "108": "/r/AngelsBaseball",
                        "136": "/r/Mariners",
                        "111": "/r/RedSox",
                        "147": "/r/NYYankees",
                        "141": "/r/TorontoBlueJays",
                        "139": "/r/TampaBayRays",
                        "110": "/r/Orioles",
                        "138": "/r/Cardinals",
                        "113": "/r/Reds",
                        "134": "/r/Buccos",
                        "112": "/r/CHICubs",
                        "158": "/r/Brewers",
                        "137": "/r/SFGiants",
                        "109": "/r/azdiamondbacks",
                        "115": "/r/ColoradoRockies",
                        "119": "/r/Dodgers",
                        "135": "/r/Padres",
                        "143": "/r/Phillies",
                        "121": "/r/NewYorkMets",
                        "146": "/r/letsgofish",
                        "120": "/r/Nationals",
                        "144": "/r/Braves"
                    }
                    if field == "sublink": return "[" + team.get('name_abbrev') + "](" + subs.get(team_id) + ")"
                    else: return subs.get(team_id)
                else:
                    return team.get(field)

        if self.SETTINGS.get('LOG_LEVEL')>1: print "WARNING: Couldn't look up",field,"from",lookupfield,"=",lookupval + ", returning None..."
        return None

    def lookup_player_info(self, id, field, field2=None):
            if not id: return None
            playerdata = self.api_download('/api/v1/people/'+str(id),localWait=28800)
            if field=='all': return playerdata.get('people')[0]
            elif not field2: return playerdata.get('people')[0].get(field)
            else: return playerdata.get('people')[0].get(field,{}).get(field2)

    def convert_tz(self, dt, which='team'):
        if not dt.tzinfo: dt = dt.replace(tzinfo=tz.utc)
        if which=='bot':
            to_tz = tzlocal.get_localzone()
        else:
            to_tz = tz.timezone(self.lookup_team_info(field='time_zone_alt',lookupfield='team_code',lookupval=self.SETTINGS.get('TEAM_CODE')))
        return dt.astimezone(to_tz)

    def get_teams_time(self, url="", pk=0, d=datetime.today().date()):
        teams = {}
        if pk != 0 and url == "": url = "/api/v1/game/"+str(pk)+"/feed/live"

        gamelive = self.api_download(url)
        game = gamelive.get('gameData')

        if pk==0: pk = game.get('game').get('pk')
        gameDateStr = self.get_gameDate(pk,d)
        gameDate_object = datetime.strptime(gameDateStr,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=tz.utc)
        date_object = self.convert_tz(gameDate_object,'team')
        if gameDateStr.find('3:33') != -1 and game.get('game').get('doubleHeader') == 'Y' and str(game.get('game').get('gameNumber')) == "2":
            myteam = self.lookup_team_info(field='team_id',lookupfield='team_code',lookupval=self.SETTINGS.get('TEAM_CODE'))
            gameDate_object = datetime.strptime(gameDateStr,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=tzlocal.get_localzone()) #use 3:33 in local timezone or else we'll get yesterday's games
            schedule = self.get_schedule(gameDate_object)
            for schedgame in schedule:
                if (str(schedgame.get('gamePk')) != str(game.get('game').get('pk'))) and (int(myteam) in [int(schedgame.get('teams').get('home').get('team').get('id')),int(schedgame.get('teams').get('away').get('team').get('id'))]) and schedgame.get('doubleHeader') == 'Y' and int(schedgame.get('gameNumber')) == int(game.get('game').get('gameNumber'))-1:
                    othergame = self.get_teams_time(url=schedgame.get('link'),d=date_object.date())
                    gameDate_object = othergame.get('date_object_utc') + timedelta(hours=3, minutes=30)
                    if self.SETTINGS.get('LOG_LEVEL')>2: print "Detected doubleheader Game 2 start time is before Game 1 start time. Using Game 1 start time + 3.5 hours for Game 2 (",gameDate_object,")..."
                    date_object = self.convert_tz(gameDate_object,'team')
                    break
        first_pitch = date_object.strftime('%I:%M %p %Z')

        home = {}
        away = {}

        homeid = game.get('teams').get('home').get('id')
        if homeid == None: homeid = game.get('teams').get('home').get('teamID')
        homeSportCode = game.get('teams').get('home').get('sportCode')
        if homeSportCode == None:
            homeSport = self.api_download(game.get('teams').get('home').get('sport',{}).get('link'))
            if homeSport:
                homeSportCode = homeSport.get('sports')[0].get('code')
            else: homeSportCode = 'mlb'
        hometeam = self.lookup_team_info("all", "team_id", str(homeid),homeSportCode)
        home.update({'name_abbrev' : hometeam.get('name_abbrev'), 'team_code' : hometeam.get('team_code'), 'team_name' : hometeam.get('name'), 'win' : game.get('teams').get('home').get('record').get('wins'), 'loss' : game.get('teams').get('home').get('record').get('losses'), 'runs' : gamelive.get('liveData').get('linescore',{}).get('home',{}).get('runs',0), 'sport_code' : homeSportCode, 'team_id' : homeid, 'file_code' : hometeam.get('file_code')})

        awayid = game.get('teams').get('away').get('id')
        if awayid == None: awayid = game.get('teams').get('away').get('teamID')
        awaySportCode = game.get('teams').get('away').get('sportCode')
        if awaySportCode == None:
            awaySport = self.api_download(game.get('teams').get('away').get('sport',{}).get('link'))
            if awaySport:
                awaySportCode = homeSport.get('sports')[0].get('code')
            else: awaySportCode = 'mlb'
        awayteam = self.lookup_team_info("all", "team_id", str(awayid),awaySportCode)
        away.update({'name_abbrev' : awayteam.get('name_abbrev'), 'team_code' : awayteam.get('team_code'), 'team_name' : awayteam.get('name'), 'win' : game.get('teams').get('away').get('record').get('wins'), 'loss' : game.get('teams').get('away').get('record').get('losses'), 'runs' : gamelive.get('liveData').get('linescore',{}).get('away',{}).get('runs',0), 'sport_code' : awaySportCode, 'team_id' : awayid, 'file_code' : awayteam.get('file_code')})

        teams.update({'home' : home, 'away' : away, 'time' : first_pitch, 'status': game.get('status'), 'date_object' : date_object, 'date_object_utc' : gameDate_object})

        if self.SETTINGS.get('LOG_LEVEL')>2: print "Returning teams and time for specified game..."
        return teams
