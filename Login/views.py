from django.shortcuts import render,HttpResponse,redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login,logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from io import StringIO
from django.conf import settings
import csv
import os
from dotenv import load_dotenv
load_dotenv()
# Replace with your API key
API_KEY = os.getenv('API_KEY')

youtube = build('youtube', 'v3', developerKey=API_KEY)



# Create your views here.
@login_required(login_url='index')
def HomePage(request):
    return render(request,'home.html')
    
def IndexPage(request):
    return render(request,'index.html')

def SingUpPage(request):
    if request.method == 'POST':
        uname = request.POST.get('uname')
        firstname = request.POST.get('fname')
        lastname = request.POST.get('lname')
        email = request.POST.get('email')
        pass1 = request.POST.get('pass1')
        pass2 = request.POST.get('pass2')

        if User.objects.filter(username=uname).exists():
            messages.warning(request, "User Name Already taken. Try using a different username.")
        elif pass1 != pass2:
            messages.warning(request, "Check your confirm Password")
        else:
            # Adjust the order of arguments when calling create_user
            my_user = User.objects.create_user(uname, email, pass1, first_name=firstname, last_name=lastname)
            my_user.save()
            messages.success(request, "Account created successfully. You can now log in.")
            return redirect('login')
    return render(request, 'singup.html')

def LogoutPage(request):
    logout(request)
    return redirect('index')
# myapp/views.py

import requests
from django.conf import settings
from django.shortcuts import render
import requests
import csv
import re
@login_required(login_url='index')


def Y_R(request):
    if request.method == 'POST':
        try:
            # Check if the device is online by making a simple HTTP request
            requests.get('https://www.google.com', timeout=5)

            # Get the topic from the POST request
            user_topic = request.POST.get('YouTube')

            # Load the CSV file to check if the topic is supported
            csv_file_path = settings.BASE_DIR / 'static/Book.csv'  # Specify the path to your CSV file
            topic_supported = False

            with open(csv_file_path, 'r', newline='', encoding='utf-8') as csv_file:
                csv_reader = csv.reader(csv_file)
                for row in csv_reader:
                    if row:  # Check if the row is not empty
                        # Check 'past_studies' and 'recommended_topics' fields for the user-provided topic
                        for field in (row[1], row[2]):  # Assuming 'past_studies' is at index 1 and 'recommended_topics' is at index 2
                            if field:
                                topics = [topic.strip().lower() for topic in field.split(',')]
                                if user_topic.lower() in topics:
                                    topic_supported = True
                                    break
                        
                        if topic_supported:
                            break
            
            if not topic_supported:
                # Topic is not supported, display message
                offline_message = f"The topic '{user_topic}' is not supported."
                context = {
                    'offline_message': offline_message,
                }
                return render(request, 'meterial.html', context)
            
            # Continue with the YouTube API request if topic is supported
            search_response = youtube.search().list(
                q=user_topic,
                type='video',
                part='id,snippet',
                maxResults=5,
                videoDuration='any'  # Can be 'any', 'long', 'medium', 'short'
            ).execute()

            links = []
            topics = []
            for video in search_response['items']:
                # Filtering out short videos (less than 1 minute)
                video_id = video['id']['videoId']
                video_details = youtube.videos().list(
                    part='contentDetails',
                    id=video_id
                ).execute()

                duration = video_details['items'][0]['contentDetails']['duration']
                # Convert ISO 8601 duration to seconds
                duration_in_seconds = iso8601_duration_to_seconds(duration)
                
                if duration_in_seconds >= 60:  # Exclude videos shorter than 1 minute
                    topic = f"{video['snippet']['title']}"
                    link = f"https://www.youtube.com/watch?v={video['id']['videoId']}\n"
                    topics.append(topic)
                    links.append(link)

            zipped_lists = zip(topics, links)
            context = {
                'zipped_lists': zipped_lists,
            }

            return render(request, 'meterial.html', context)

        except requests.ConnectionError:
            # Handle the case when the device is offline
            offline_message = "The device is currently offline. Please check your internet connection."
            context = {
                'offline_message': offline_message,
            }

            return render(request, 'meterial.html', context)

    return render(request, 'meterial.html')

def iso8601_duration_to_seconds(duration):
    """
    Parse an ISO 8601 duration string and return the total duration in seconds.
    """
    match = re.match(r'PT(\d+H)?(\d+M)?(\d+S)?', duration)
    hours = int(match.group(1)[:-1]) if match.group(1) else 0
    minutes = int(match.group(2)[:-1]) if match.group(2) else 0
    seconds = int(match.group(3)[:-1]) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds

@login_required(login_url='index')
def get_recommendations(request):
    if 'user_input' in request.GET:
        recommendations = {}
        user_input = request.GET['user_input']
        user_inputs = [topic.strip() for topic in user_input.split(',')]

        # Load data from the CSV file
        df = pd.read_csv('static/Book.csv')

        # Ensure 'past_studies' column is of string type
        df['past_studies'] = df['past_studies'].astype(str)

        # Add the user's input to the DataFrame
        user_data = pd.DataFrame({'user_id': [999], 'past_studies': [user_input]})
        df = pd.concat([df, user_data], ignore_index=True)

        # Convert past_studies to TF-IDF vectors
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(df['past_studies'])

        # Compute cosine similarity between TF-IDF vectors
        cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)

        # Get the index of the user
        user_index = df[df['user_id'] == 999].index[0]

        # Get the cosine similarity scores for the user
        sim_scores = list(enumerate(cosine_sim[user_index]))

        # Sort the users based on similarity scores
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

        # Get the top similar users
        sim_users = sim_scores[1:4]

        # Extract recommended topics from similar users
        recommended_topics = set()
        for sim_user in sim_users:
            # Ensure 'recommended_topics' column is of string type
            topics_str = str(df.loc[sim_user[0], 'recommended_topics'])
            recommended_topics.update(topics_str.split(', '))

        recommendations[user_input] = list(recommended_topics)[:3]

        return render(request, 'recommendations_form.html', {'user_input': user_input, 'recommendations': recommendations})
    username = request.user.first_name
    return render(request, 'recommendations_form.html', {'username': username})
def logini(request):
    if request.method=='POST':
        username=request.POST.get('username')
        passw=request.POST.get('pass')
        log=authenticate(request,username=username,password=passw)
        if log is not None:
            login(request,log)
            return redirect('home')
        else:
            messages.warning(request,"Cheack Your Password or username")
    return render(request,'login.html')
