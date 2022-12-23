# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2022 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""
__author__ = "GVE DevNet<gvedevnet@cisco.com>"
__copyright__ = "Copyright (c) 2022 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

import os
import urllib
import humanize
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect,session
from tempfile import TemporaryDirectory
from sharepoint import Sharepoint

load_dotenv()

global webex_access_token
WEBEX_BASE_URL = "https://webexapis.com/v1"

# Webex integration credentials
webex_integration_client_id = os.getenv("webex_integration_client_id")
webex_integration_client_secret= os.getenv("webex_integration_client_secret")
webex_integration_redirect_uri = os.getenv("webex_integration_redirect_uri")
webex_integration_scope = os.getenv("webex_integration_scope")

app = Flask(__name__)
app.secret_key=os.getenv('FLASK_SECRET_KEY')

##########################################
# Context Processor for Jinja Templating
##########################################
@app.context_processor
def utility_processor():
    def readable_size(units):
        return humanize.naturalsize(units,format='%.2f')
    def readable_time(timeunits):
        return humanize.naturaltime(timeunits).replace("T"," ").replace("Z","")
    def total_meeting_size(meets):
        total_size=0
        for meet in meets:
            total_size+=meet["sizeBytes"]
        return total_size
    return dict(readable_size=readable_size,readable_time=readable_time,total_meeting_size=total_meeting_size,app_title=os.getenv('FLASK_APP_TITLE'))

##########################################
# Routes
##########################################
@app.route('/')
def home():
    return render_template('home.html')

# Handle Webex oauth
@app.route('/webexlogin', methods=['POST'])
def webexlogin():
    WEBEX_USER_AUTH_URL = WEBEX_BASE_URL + "/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&response_mode=query&scope={scope}".format(
        client_id=urllib.parse.quote(webex_integration_client_id),
        redirect_uri=urllib.parse.quote(webex_integration_redirect_uri),
        scope=urllib.parse.quote(webex_integration_scope)
    )

    return redirect(WEBEX_USER_AUTH_URL)

# Main page of the app
@app.route('/webexoauth', methods=['GET'])
def webexoauth():
    global sites
    global webex_access_token
    global people

    webex_code = request.args.get('code')
    webex_access_token = get_webex_access_token(webex_code)

    sites = get_sites()
    people= get_people(webex_access_token)

    return render_template('listings.html', sites=sites, people=people)

# Step 1: select period of recordings
@app.route('/select_period', methods=['POST', 'GET'])
def select_period():
    global sites
    global selected_site
    global selected_person_id
    global meetings

    if request.method == 'POST':
        form_data = request.form
        app.logger.info(form_data)

        from_date = form_data['fromdate']
        to_date = form_data['todate']
        selected_site = form_data['site']
        selected_person_id = form_data['person']
        host_email = get_host_email(selected_person_id)[0]

        meetings = get_meetings(from_date, to_date, selected_site, host_email)

        app.logger.info("Successfully retrieved the list of recordings")

        return render_template('listings.html', sites=sites, selected_site = selected_site, meetings = meetings, people=people, selected_person_id=selected_person_id)
    return render_template('listings.html')

# Step 2: Select recordings to migrate from Webex to Sharepoint
@app.route('/select_recordings', methods=['POST', 'GET'])
def select_recordings():
    global sites
    global selected_site
    global meetings
    global selected_person_id

    if request.method == 'POST':
        form_data = request.form
        app.logger.info(form_data)

        failed_migration_IDs = []
        meetings_to_migrate = []
        successfully_migrated = []

        if 'meeting_id' in form_data:
            form_dict = dict(form_data.lists())
            meetings_to_migrate = form_dict['meeting_id']
            app.logger.info(meetings_to_migrate)
            temp_directory=TemporaryDirectory(suffix="-recordings")
            sp = Sharepoint()
            for meeting in meetings_to_migrate:
                topic=""
                try:
                    recording_details = get_recording_details(meeting, selected_person_id)

                    app.logger.info(f"Downloading recording with meeting ID: {meeting}")

                    # Download recording mp4 in memory
                    downloadlink = recording_details['temporaryDirectDownloadLinks']['recordingDownloadLink']
                    topic = recording_details['topic']
                    downloaded_file = urllib.request.urlopen(downloadlink)


                    temp_file_name=os.path.join(temp_directory.name,topic.replace(" ","_")+'.mp4')
                    app.logger.info(temp_file_name)
                    with open(temp_file_name,'wb+') as fp:
                        fp.write(downloaded_file.read())

                    file_status=sp.upload_files(os.getenv('RECORDINGS_FOLDER'),temp_file_name)
                    failed_migration_IDs.append({"id":meeting,"name":topic,"status_code":file_status.status_code})
                    app.logger.debug(file_status,file_status.text)
                except Exception as err:
                    failed_migration_IDs.append({"id":meeting,"name":topic,"status_code":err.text})
                    app.logger.error(f"Failed migration of recording with meeting id {meeting}")

            temp_directory.cleanup()
        return render_template('listings.html', sites=sites, selected_site = selected_site, meetings = meetings, people=people, selected_person_id=selected_person_id, failed_meetings=failed_migration_IDs)
    else:
        return render_template('listings.html',sites=sites, selected_site = selected_site, meetings = meetings, people=people, selected_person_id=selected_person_id)

########################
### Helper Functions ###
########################

# Get Webex Access Token
def get_webex_access_token(webex_code):
    headers_token = {
        "Content-type": "application/x-www-form-urlencoded"
    }
    body = {
        'client_id': webex_integration_client_id,
        'code': webex_code,
        'redirect_uri': webex_integration_redirect_uri,
        'grant_type': 'authorization_code',
        'client_secret': webex_integration_client_secret
    }
    get_token = requests.post(WEBEX_BASE_URL + "/access_token?", headers=headers_token, data=body)

    webex_access_token = get_token.json()['access_token']
    return webex_access_token

# Get all the sites
def get_sites():
    # Get site URLs
    url = f"{WEBEX_BASE_URL}/meetingPreferences/sites"
    headers = {
        "Authorization" : f"Bearer {webex_access_token}"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    sites = response.json()['sites']
    return sites

# Get all the meetings from a selected period, site and specific user in your organization
def get_meetings(from_date, to_date, selected_site, host_email):
    # Get recordings
    url = f"{WEBEX_BASE_URL}/recordings?from={from_date}T00%3A00%3A00&to={to_date}T23%3A59%3A59&siteUrl={selected_site}&hostEmail={host_email}"
    headers = {
        "Authorization" : f"Bearer {webex_access_token}"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    meetings = response.json()['items']
    return meetings


# Get all the people in your organization
def get_people(webex_access_token):
    # Get people
    url = f"{WEBEX_BASE_URL}/people"
    headers = {
        "Authorization": f"Bearer {webex_access_token}"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    people = response.json()['items']
    return people


# Get the host email from the people details
def get_host_email(person_id):
    # Get people details
    url = f"{WEBEX_BASE_URL}/people/{person_id}"
    headers = {
        "Authorization": f"Bearer {webex_access_token}"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    app.logger.debug("get host email",response.json())
    emails = response.json()["emails"]
    return emails


# Get the recording details based on a meeting_id
def get_recording_details(meeting, selected_person_id):
    # Get recording details
    url = f"{WEBEX_BASE_URL}/recordings/{meeting}?hostEmail={get_host_email(selected_person_id)[0]}"
    response = requests.get(url, headers = {
        "Authorization" : f"Bearer {webex_access_token}"
    })
    return response.json()



if __name__ == "__main__":
    app.run()