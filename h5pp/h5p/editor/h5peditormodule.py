# Django module h5p editor

import shutil
import time
import json
import os
import re

from django.contrib.sites.models import Site
from django.conf import settings

from h5pp.models import h5p_content_user_data, h5p_libraries, h5p_points
from h5pp.h5p.h5pmodule import h5pAddCoreAssets, h5pAddFilesAndSettings
from h5pp.h5p.h5pclasses import H5PDjango


STYLES = ["libs/darkroom.css",
          "styles/css/application.css"]

SCRIPTS = [
    "scripts/h5peditor.js",
    "scripts/h5peditor-semantic-structure.js",
    "scripts/h5peditor-editor.js",
    "scripts/h5peditor-library-selector.js",
    "scripts/h5peditor-form.js",
    "scripts/h5peditor-text.js",
    "scripts/h5peditor-html.js",
    "scripts/h5peditor-number.js",
    "scripts/h5peditor-textarea.js",
    "scripts/h5peditor-file-uploader.js",
    "scripts/h5peditor-file.js",
    "scripts/h5peditor-image.js",
    "scripts/h5peditor-image-popup.js",
    "scripts/h5peditor-av.js",
    "scripts/h5peditor-group.js",
    "scripts/h5peditor-boolean.js",
    "scripts/h5peditor-list.js",
    "scripts/h5peditor-list-editor.js",
    "scripts/h5peditor-library.js",
    "scripts/h5peditor-library-list-cache.js",
    "scripts/h5peditor-select.js",
    "scripts/h5peditor-dimensions.js",
    "scripts/h5peditor-coordinates.js",
    "scripts/h5peditor-none.js",
    "ckeditor/ckeditor.js"]


def h5peditorContent(request):
    assets = h5pAddCoreAssets()
    coreAssets = h5pAddCoreAssets()
    editor = h5pAddFilesAndSettings(request, True)
    framework = H5PDjango(request.user)
    add = list()

    for style in STYLES:
        css = settings.STATIC_URL + 'h5p/h5peditor/' + style
        assets['css'].append(css)

    for script in SCRIPTS:
        if script != 'scripts/h5peditor-editor.js':
            js = settings.STATIC_URL + 'h5p/h5peditor/' + script
            assets['js'].append(js)

    add.append(settings.STATIC_URL +
               'h5p/h5peditor/scripts/h5peditor-editor.js')
    add.append(settings.STATIC_URL + 'h5p/h5peditor/application.js')

    languageFile = settings.STATIC_URL + \
        'h5p/h5peditor/language/' + settings.H5P_LANGUAGE + '.js'
    if not os.path.exists(settings.BASE_DIR + languageFile):
        languageFile = settings.STATIC_URL + 'h5p/h5peditor/language/en.js'

    add.append(languageFile)

    contentValidator = framework.h5pGetInstance('contentvalidator')
    editor['editor'] = {
        'filesPath': settings.MEDIA_URL + 'h5pp/editor',
        'fileIcon': {
            'path': "{}/{}h5p/h5peditor/images/binary-file.png".format(Site.objects.get_current().domain, settings.STATIC_URL),
            'width': 50,
            'height': 50
        },
        'ajaxPath': "{}editorajax/{}/".format(settings.H5P_URL, (request['contentId'] if 'contentId' in request else '0')),
        'libraryPath': "{}{}h5p/h5peditor/".format(Site.objects.get_current().domain, settings.STATIC_URL),
        'copyrightSemantics': contentValidator.getCopyrightSemantics(),
        'assets': assets,
        'contentRelUrl': '../media/h5pp/content/'
    }

    return {'editor': json.dumps(editor), 'coreAssets': coreAssets, 'assets': assets, 'add': add}

##
# Retrieves ajax parameters for content and update or delete
##


def handleContentUserData(request):
    framework = H5PDjango(request.user)
    core = framework.h5pGetInstance('core')
    contentId = request.GET['contentId']
    subContentId = request.GET['subContentId']
    dataId = request.GET['dataType']

    if contentId == None or dataId == None or subContentId == None:
        return ajaxError('Missing parameters')

    if 'data' in request.POST and 'preload' in request.POST and 'invalidate' in request.POST:
        data = request.POST['data']
        preload = request.POST['preload']
        invalidate = request.POST['invalidate']

        # Saving data
        if data != None and preload != None and invalidate != None:
            if data == '0':
                # Delete user data
                deleteUserData(contentId, subContentId,
                               dataId, request.user.id)
            else:
                # Save user data
                saveUserData(contentId, subContentId, dataId,
                             preload, invalidate, data, request.user.id)

            return ajaxSuccess()
    else:
        # Fetch user data
        userData = getUserData(contentId, subContentId,
                               dataId, request.user.id)
        if userData == False:
            # Did not find data, return nothing
            return ajaxSuccess()
        else:
            # Found data, return encoded data
            return ajaxSuccess(userData['data'])

    return

##
# Get user data for content
##


def getUserData(contentId, subContentId, dataId, userId):
    result = h5p_content_user_data.objects.filter(
        user_id=userId, content_main_id=contentId, sub_content_id=subContentId, data_id=dataId).values()
    return result[0] if len(result) > 0 else False

##
# Save user data for specific content in database
##


def saveUserData(contentId, subContentId, dataId, preload, invalidate, data, userId):
    update = getUserData(contentId, subContentId, dataId, userId)

    preload = 0 if preload == '0' else 1
    invalidate = 0 if invalidate == '0' else 1

    if not update:
        h5p_content_user_data.objects.create(
            user_id=userId,
            content_main_id=contentId,
            sub_content_id=subContentId,
            data_id=dataId,
            timestamp=time.time(),
            data=data,
            preloaded=preload,
            delete_on_content_change=invalidate
        )
    else:
        newDataId = update['id']
        userData = h5p_content_user_data.objects.get(id=update['id'])
        userData.user_id = userId
        userData.content_main_id = contentId
        userData.sub_content_id = subContentId
        userData.data_id = dataId
        userData.data = data
        userData.preloaded = preload
        userData.delete_on_content_change = invalidate
        userData.save()

##
# Delete user data with specific content from database
##


def deleteUserData(contentId, subContentId, dataId, userId):
    h5p_content_user_data.objects.get(
        user_id=userId, content_main_id=contentId, sub_content_id=subContentId, data_id=dataId).delete()

##
# Create or update H5P content
##


def createContent(request, content, params):
    framework = H5PDjango(request.user)
    editor = framework.h5pGetInstance('editor')
    contentId = content['id']

    if not editor.createDirectories(contentId):
        print('Unable to create content directory.', 'error')
        return False

    editor.processParameters(contentId, content['library'], params)

    return True


def getLibraryProperty(library, prop='all'):
    matches = re.search('(.+)\s(\d+)\.(\d+)$', library)
    if matches:
        libraryData = {
            'machineName': matches.group(1),
            'majorVersion': matches.group(2),
            'minorVersion': matches.group(3)
        }
        if prop == 'all':
            return libraryData
        elif prop == 'libraryId':
            temp = h5p_libraries.objects.filter(machine_name=libraryData['machineName'], major_version=libraryData[
                                                'majorVersion'], minor_version=libraryData['minorVersion']).values('library_id')
            return temp
        else:
            return libraryData[prop]
    else:
        return False

def ajaxSuccess(data=None):
    response = {
        'success': True
    }
    if data != None:
        response['data'] = data

    return json.dumps(response)


def ajaxError(message=None):
    response = {
        'success': False
    }
    if message != None:
        response['message'] = message

    return json.dumps(response)
