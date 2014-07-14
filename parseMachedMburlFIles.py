'''
Created on Oct 9, 2013

A tool that finds for each symbTr composition  a list of recordings from MusicBrainz db  

A local copy of symbTr files path should be given in var symbTrDir 
Qurying is done on a copy of whole MB collection 

first matching between symbTr composition and its MB-composition ID is done
-Checks for empty files in a given path
-checks whether audio exists by checking in list of IDs
-checks if songs are sarki.

@author: georgi 
'''

import os
import sys

import compmusic.file
import eyed3

import musicbrainzngs as mb
import sertanscores
from musicBrainz import sertanscores


import argparse
import collections
import unidecode
import shutil
import random
import functools32
import json
import string

import Levenshtein
import re

import compmusic.musicbrainz
from IPython.lib.pretty import pprint

import requests
from compmusic.file import mb_artist_id


mb.set_useragent("Dunya", "0.1")
mb.set_rate_limit(False)
mb.set_hostname("sitar.s.upf.edu:8090")

# global vars: 
pathToDunyaServer = "http://dunya.compmusic.upf.edu/document/by-id/";
rootTargetdir="resultsMatchedVocalOnly"
symbTrDir = "/Users/joro/Documents/Phd/UPF/symbTr"


# browse files from all subdirs
def GetFileNamesInDir(dir_name, ext=".mburl.id.uniq", skipFoldername = ''):
    names = []
    folders = []
    print dir_name
    for (path, dirs, files) in os.walk(dir_name):
        for f in files:
            if ext in f.lower():
                if skipFoldername not in path.split(os.sep)[1:]:
                    names.append(f)
                    folders.append(path)
    return folders, names


def isItSarki(fileURL):
    return '--sarki--' in fileURL

''' check if the release (album) of the recording is not in list with missing releases
Current as of January 2014, missing releases are these with no audio. 
Check dunya dashboard to find current missing ones
'''
def getExistigReleasesForRecording(recording, recID):

# load list
    ListNonExistingReleases= [u'44da2fd9-0b2b-4b93-937c-39d7575ae14a',
   u'3f73b971-7072-4fb8-af39-52696876f4cf',
   u'cd5da55a-2845-42d9-942e-a0d040ac22b3',
   u'41576df9-369c-43de-831f-c1996e3b57ef',
   u'1f3152fd-7749-4b5b-9fc4-7576678cec59',
   u'2d29999b-732d-4a8e-bcc0-8ef7ecf1308b',
   u'4469247f-6e65-4a35-8661-321c399dacb9',
   u'732f33fc-c373-46d2-a09a-545c03469766',
   u'0b7019b7-ca2a-4eaf-90eb-98c4621953b0',
   u'6777da65-efe1-4874-ba36-18fb56d506e9',
   u'bbfefac2-c0a1-46a3-82ff-20c60c79a6e7',
   u'c901447d-f986-489e-9a2b-1d42958aa05a',
   u'def8324c-f183-437e-b51e-76e3b2129707',
   u'a01eacba-007b-47fe-b1a2-5911482bafa7',
   u'9f96b18f-ab6f-454f-a49e-06268da252ec',
   u'55b20427-c7a5-4e8b-a26f-c6096fb69eeb',
   u'b2846496-340b-4602-82a1-c5a55d4ffb04',
   u'90897679-104a-4e07-a0a9-88d3a3c91cde',
   u'c86226bc-cecb-4848-bf6e-4cf58549a92d'] 
    
#     allReleases = mb.get_releases_in_collection("5bfb724f-7e74-45fe-9beb-3e3bdb1a119e")

    dictRec = recording["recording"]
    
    if not dictRec.has_key("release-list"):
            print "Special case: recording id ", recID, " has no releases associated with it"
            return []
    
    release_list = dictRec["release-list"]
    
    #result 
    existingReleaseLists = []
    
#     print "DEBUG: RELEASEs are %", len(release_list)
    
    for release in  release_list:
        if (not release["id"] in ListNonExistingReleases):
            existingReleaseLists.append(release)

    
    return existingReleaseLists



# if any type of artist is vocal returns true
def isRecordingWithVocals(recording, recordingID):
    
    dictRec = recording["recording"]
    if not dictRec.has_key("artist-relation-list"):
        print "Special case: recording id ", recordingID, " has no artist-relation list"
        return False

    
    art_rel_list = dictRec["artist-relation-list"]
    for art_relation in  art_rel_list:
        if (art_relation["type"] == "vocal"):
            return True
#    otherwise return false
    return False

# returns the list of recordings with existing for a given music brainz workID
def getRecrodingListForAWork( workMBID, m):
    
   
    # get list of recording IDa for work ID
    recordingIDsList = m.recordingids_for_work(workMBID)       
                       
        
               
    existingVocalRecordings = [];
    for recID in recordingIDsList:
        
        recording = mb.get_recording_by_id(recID, includes=["artist-rels", "releases"])

        # check if we have the realease of the recording in the database 
        listExistingReleases = getExistigReleasesForRecording(recording, recID)
        if len(listExistingReleases) == 0:
            continue
                
#         check if we have vocals                         
        if not isRecordingWithVocals(recording, recID):
                        print "no vocals in recording ID: ", recID
        else: 
            existingVocalRecordings.append(recID)            
                                
                        
                                  
 
    
    return existingVocalRecordings




def getMBWorkIDFromFile( fileURL):
    


    # if some match found process
    if os.stat(fileURL)[6] == 0:
        return []
# 1. check whether sarki
    if not isItSarki(fileURL):
        return []
# here get id from mburl
    fileHandle = open(fileURL, "r")
# take only first line since ID is sometimes doubled by mistake
    workMBIDs = fileHandle.readlines()
    
    fileHandle.close();
    
    return workMBIDs

# downloads audio for given rec id. From Dunya server

def downloadAudio(recID, targetDir):
    urlAudio= '{0}/{1}.mp3'.format(pathToDunyaServer, recID)
    fname = os.path.basename(urlAudio)
    httpResponseBody = requests.get(urlAudio)
    
    # write the file
    localUrlAudio= os.path.join(targetDir,fname)
    open(localUrlAudio, "wb").write(httpResponseBody.content)
    
    return localUrlAudio

def makeDir(symbTrNameNoExt):
    targetDir = os.path.join(rootTargetdir, symbTrNameNoExt)
    try:
        os.makedirs(targetDir)
    except:
        pass
    return targetDir


def saveScores(symbTrNameNoExt, symbTrDir, targetDir):
    
    
    try:
        shutil.copy(os.path.join(symbTrDir, symbTrNameNoExt+".txt"), targetDir)
    except IOError:
        pass
    
    try:
        shutil.copy(os.path.join(symbTrDir, symbTrNameNoExt+".pdf"), targetDir)
    except IOError:
        pass
    
    return targetDir


   # saves the audio with a name according to the release name
def saveAudio(targetDir, listRecIDs):
    
    isThereAtLeastOneAudioFIle=False
    
    # download audio
    for recID in listRecIDs:
        localUrlAudio = downloadAudio(recID, targetDir)
        
        # rename according to release and artist
        try:
            metadata = compmusic.file_metadata(localUrlAudio)
        except Exception: 
            pass
            print "symbTr file ", targetDir, " and recID ", recID,  " has Problem with metadata...", "\n" 
            os.remove(localUrlAudio)
            continue
            
        
        artistName = metadata["meta"]["artist"]
        artistName = unidecode.unidecode(artistName)
        
        releaseName = metadata["meta"]["release"]
        releaseName = unidecode.unidecode(releaseName)
        
        titleName = metadata["meta"]["title"]
        titleName = unidecode.unidecode(titleName)
        titleName = titleName.replace("/", "__")
        
       
        fileName = '{0}.mp3'.format(titleName)
        newDirUrl = '{0}/{1}--{2}'.format(targetDir, artistName , releaseName)
        if not os.path.exists(newDirUrl): os.makedirs(newDirUrl)
        
        newLocalUrlAudio = os.path.join(newDirUrl,fileName )
        shutil.move(localUrlAudio, newLocalUrlAudio)
        isThereAtLeastOneAudioFIle = True
       
        
    return isThereAtLeastOneAudioFIle 
        

    



def getAllRecordingsInCollection(collectionName):
    ''' get all recordings from a given collection '''
    
    allRecordings = []
    # TODO: for a given collection give me all releases
                 
    # TODO: for a given release give me all recordings           
        

    return allRecordings
  
    
'''        
# returns the list of recordings from given list
'''
def getOnlyVocalRecording(recordingIDsList):
    
    

    existingVocalRecordings = [];

    for recID in recordingIDsList:
        
        recording = mb.get_recording_by_id(recID, includes=["artist-rels", "releases"])

        # check if we have the realease of the recording in the database 
        listExistingReleases = getExistigReleasesForRecording(recording, recID)
        if len(listExistingReleases) == 0:
            continue
                
#         check if we have vocals                         
        if not isRecordingWithVocals(recording, recID):
                        print "no vocals in recording ID: ", recID
        else: 
            existingVocalRecordings.append(recID)         
                                  


def doitNoFileSave():
    sarkisWithScores = {}
    totalCounterRecordings=0
    counterWorks=0
     
    counterIter = 0    
        
    [folders, names ] = GetFileNamesInDir(symbTrDir)    
    
# DEBUG:
#     names=names[:100]
# EDN DEBUG


    # init
    makamScore = sertanscores. MakamScore(' ', ' ', ' ', ' ')      
   
    for name in names:
        
        counterIter += 1
#         print 'DEBUG: at iter %d of %d ', counterIter, len(names)

        # combine path and file: 

        fileURL = os.path.join(folders[0], name)
        
        workMBIDs = getMBWorkIDFromFile(fileURL)
        
        
        allExistingVocalRecordings = []; 
        for workMBID in workMBIDs:
            workMBID=workMBID.strip()
        
           
            existingVocalRecordings = getRecrodingListForAWork(workMBID, makamScore)
            if len(existingVocalRecordings) == 0:
                continue
        
            nameNoExt = os.path.basename(name)
            nameNoExt = os.path.splitext(nameNoExt)[0]
            nameNoExt = os.path.splitext(nameNoExt)[0]
            nameNoExt = os.path.splitext(nameNoExt)[0]
            nameNoExt = os.path.splitext(nameNoExt)[0]
        
            makamScore.save_scores(nameNoExt, existingVocalRecordings)
            
            allExistingVocalRecordings.append(existingVocalRecordings)
                                  
             
                              
    # count works with at least one recording, count total recordings
        if not len(allExistingVocalRecordings)==0:
            totalCounterRecordings = totalCounterRecordings + len(allExistingVocalRecordings)
                    
            sarkisWithScores[fileURL] = allExistingVocalRecordings
            
            
    # at the end
    print "total num sarkis =" , len(sarkisWithScores)
    print "total num recordings with audio =" ,  totalCounterRecordings
       
    for key, value in sorted(sarkisWithScores.items()):
        if len(value)==1:
            if not value[0] :
                continue
        print("{} : \t {}".format(key, value))
        print 




def doit():

   #####################
   #  load all sarki names 
   ###################  
    counterIter = 0    
        
    [folders, names ] = GetFileNamesInDir(symbTrDir)    
    
# DEBUG test with only 100:
#     names=names[:100]
# END DEBUG


    #### init  
    makamScore = sertanscores. MakamScore(' ', ' ', ' ', ' ')      
   
    for symbTrName in names:
        
        counterIter += 1
       
        print 'DEBUG: at iter %d of %d ', counterIter, len(names)

        # combine path and file: 

        fileURL = os.path.join(folders[0], symbTrName)
        
        
     
        
        workMBIDs = getMBWorkIDFromFile(fileURL)
        
        # list of  recording ids
        allVocalRecordings = []; 
        
        
        for workMBID in workMBIDs:
            workMBID=workMBID.strip()
            
            ##################### ##########
            ## list recordings for a work
            #################################
            
            listVocalRecordingsForWork = getRecrodingListForAWork(workMBID, makamScore)
            
            if len(listVocalRecordingsForWork) == 0:
                continue
  
            for vocalRec in listVocalRecordingsForWork:
                allVocalRecordings.append(vocalRec)
        
        
        
        ##########################
        ### save scores
        #########################    
        if len(allVocalRecordings) != 0:
            
            # save scores 
            symbTrNameNoExt = os.path.basename(symbTrName)
            symbTrNameNoExt = os.path.splitext(symbTrNameNoExt)[0]
            symbTrNameNoExt = os.path.splitext(symbTrNameNoExt)[0]
            symbTrNameNoExt = os.path.splitext(symbTrNameNoExt)[0]
            symbTrNameNoExt = os.path.splitext(symbTrNameNoExt)[0]
            
            targetDir = makeDir(symbTrNameNoExt)

            # save audio
            if (not saveAudio(targetDir, allVocalRecordings)):
                shutil.rmtree(targetDir)
                continue
            
            saveScores(symbTrNameNoExt, symbTrDir, targetDir )




doit()


