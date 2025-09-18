import os
import json
import re
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

import google.generativeai as genai
from .models import BlogPost

# Load environment variables
load_dotenv()

# Configure APIs
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
# ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
# aai.settings.api_key = ASSEMBLYAI_API_KEY
from youtube_transcript_api import YouTubeTranscriptApi

def validate_and_extract_video_id(url: str) -> str:
    """Validate YouTube URL and extract video ID."""
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url)
    hostname = parsed.hostname.lower() if parsed.hostname else ''
    path = parsed.path

    if 'youtube.com' not in hostname and 'youtu.be' not in hostname:
        return None

    if 'youtu.be' in hostname:
        return path[1:] if len(path) > 1 else None

    if 'youtube.com' in hostname:
        if path == '/watch':
            qs = parse_qs(parsed.query)
            return qs.get('v', [None])[0]
        elif path.startswith('/embed/') or path.startswith('/v/'):
            parts = path.split('/')
            return parts[2] if len(parts) > 2 else None

    return None



def fetch_transcript(video_id: str, languages=['en', 'mr','hi']) -> str:
    try:
        ytt_api = YouTubeTranscriptApi()
        fetched_transcript = ytt_api.fetch(video_id, languages=languages)
        return " ".join([snippet.text for snippet in fetched_transcript])
    except Exception as e:
        print(f"Transcript fetch error: {e}")
        return None




def generate_blog_from_transcription(transcription: str) -> str:
    """
    Generate a blog or appropriate summary from a YouTube transcript using Gemini API.
    Title is provided by the user, so this only returns blog/summary content.
    """

    prompt = f"""
    You are an expert content generator.  
    You will receive the transcript of a YouTube video.  

    ### Main Task:
    Based on the type of video, decide the best output format:

    1. **If video is Educational / Tutorial / Tech Review / Documentary / Interview / Lifestyle / Explainer** →  
       Generate a **well-structured blog post** with: Introduction, Main Body, Key Takeaways, Conclusion.  

    2. **If video is a Song / Music Video / Album Track** →  
       Instead of a blog, return a **music summary** including:  
       - Song name (if available)  
       - Artist(s)  
       - Genre & mood  
       - Main theme / message  

    3. **If video is a Sports Match / Cricket / Football / Highlights** →  
       Return a **match summary** including:  
       - Teams playing  
       - Key highlights & turning points  
       - Star performers  
       - Final outcome / result (if present)  

    4. **If video does not fit any category (random memes, trailers, pranks, short ads, etc.)** →  
       Return a **brief descriptive summary** of what the video is about, instead of forcing a blog.  

    ### Input Transcript:
    {transcription}

    ### Output:
    Return only the **final blog, summary, or description** in clean Markdown.  
    Do not generate or suggest a title.
    """

    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    blog_text = response.text.strip()

    return blog_text




# View Functions
@login_required
def index(request):
    """Render the index page."""
    return render(request, 'index.html')


@csrf_exempt
def generate_blog(request):
    """Generate a blog from a YouTube video link (title is user-provided)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        data = json.loads(request.body)
        yt_link = data.get('link')
        user_title = data.get('title')

        if not yt_link or not user_title:
            return JsonResponse({'error': 'Both YouTube link and Title are required'}, status=400)

        # Step 1: Validate and parse video ID
        video_id = validate_and_extract_video_id(yt_link)
        if not video_id:
            return JsonResponse({'error': 'Invalid YouTube link'}, status=400)

        # Step 2: Fetch transcript
        transcription = fetch_transcript(video_id)
        if not transcription:
            return JsonResponse({'error': 'Failed to fetch transcript'}, status=500)

        # Step 3: Generate blog content (AI only writes blog, not title)
        try:
            blog_content = generate_blog_from_transcription(transcription)
            # print(f"User Title: {user_title}")
            # print(f"Generated Blog Content: {blog_content[:100]}...")  # preview
        except Exception as e:
            print(f"Blog generation error: {e}")
            return JsonResponse({'error': 'Failed to generate blog'}, status=500)

        # Step 4: Save blog article to DB
        new_blog = BlogPost.objects.create(
            user=request.user if request.user.is_authenticated else None,
            youtube_title=user_title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )

        # Step 5: Return JSON response
        return JsonResponse({
            'title': user_title,
            'content': blog_content,
            'blog_id': new_blog.id
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


def blog_list(request):
    """Display all blogs for the logged-in user."""
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})


def blog_details(request, pk):
    """Display details of a specific blog."""
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')


def user_login(request):
    """Handle user login."""
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')


def user_signup(request):
    """Handle user registration."""
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeat_password = request.POST['repeatPassword']

        if password == repeat_password:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = "Error occurred, make unique entries"
                return render(request, 'signup.html', {'error_message': error_message})

        error_message = "Passwords do not match"
        return render(request, 'signup.html', {'error_message': error_message})

    return render(request, 'signup.html')


def user_logout(request):
    """Handle user logout."""
    logout(request)
    return redirect('/')
