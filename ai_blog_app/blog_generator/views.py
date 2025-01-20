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
import assemblyai as aai
from pytubefix import YouTube
import google.generativeai as genai
from .models import BlogPost

# Load environment variables
load_dotenv()

# Configure APIs
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)
aai.settings.api_key = ASSEMBLYAI_API_KEY


# Utility Functions
def is_valid_youtube_link(link):
    """Validate if a link is a valid YouTube URL."""
    pattern = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/(watch\?v=)?[a-zA-Z0-9_-]+'
    return re.match(pattern, link) is not None


def yt_title(link):
    """Fetch the YouTube video title."""
    try:
        yt = YouTube(link, use_oauth=True, allow_oauth_cache=True)
        return yt.title
    except Exception as e:
        print(f"Error fetching title: {e}")
        return None


def download_audio(link):
    """Download audio from a YouTube video and convert it to MP3."""
    try:
        yt = YouTube(link, use_oauth=True, allow_oauth_cache=True)
        video = yt.streams.filter(only_audio=True).first()

        if video is None:
            raise Exception("No audio stream found")

        out_file = video.download(output_path=settings.MEDIA_ROOT)
        base, ext = os.path.splitext(out_file)
        new_file = base + '.mp3'

        if os.path.exists(new_file):
            os.remove(new_file)
        os.rename(out_file, new_file)

        return new_file
    except Exception as e:
        print(f"Audio download error: {e}")
        return None

def summarize_transcript(transcript):
    """Summarize the transcript to extract important points."""
    # Use a simple summarization model, or define a prompt to summarize
    prompt = (
        f"Summarize the following transcript into the most important points. Focus on key highlights and avoid unnecessary details:\n\n"
        f"{transcript}\n\nSummary:"
    )

    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    
    # Return the summarized content
    return response.text.strip()

def get_transcription(link):
    """Generate a shorter transcription by summarizing key points."""
    audio_file = download_audio(link)
    if not audio_file:
        raise Exception("Audio download failed")
    
    # Transcribe the audio, but focus only on the important parts
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    # Summarize the transcription to focus on key points
    summarized_transcript = summarize_transcript(transcript.text)

    # Clean up downloaded audio file
    if os.path.exists(audio_file):
        os.remove(audio_file)

    return summarized_transcript



def generate_blog_from_transcription(transcription):
    """Generate a blog article from a transcript using Gemini model."""
    prompt = (
        f"Based on the following transcript from a YouTube video, write a comprehensive blog "
        f"article containing less than 1000 words. The article should not use YouTube-specific references "
        f"but should be a proper blog:\n\n{transcription}\n\nArticle:"
    )
    model = genai.GenerativeModel('gemini-1.5-flash')
    pattern = r"\* \*\*|##|\*\*"
    response = model.generate_content(prompt)

    content = response.text.strip()
    content = re.sub(pattern, "", content, flags=re.MULTILINE)

    return content


# View Functions
@login_required
def index(request):
    """Render the index page."""
    return render(request, 'index.html')


@csrf_exempt
def generate_blog(request):
    """Generate a blog from a YouTube video link."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']

            if not is_valid_youtube_link(yt_link):
                return JsonResponse({'error': 'Invalid YouTube link'}, status=400)

            print("yt_link:", yt_link)
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        # Get YouTube title
        title = yt_title(yt_link)
        if not title:
            return JsonResponse({'error': 'Failed to fetch video title'}, status=500)
        print("title:", title)

        # Get transcription
        try:
            transcription = get_transcription(yt_link)
        except Exception as e:
            print(f"Transcription error: {e}")
            return JsonResponse({'error': 'Failed to get transcript'}, status=500)

        # Generate blog content
        try:
            blog_content = generate_blog_from_transcription(transcription)
        except Exception as e:
            print(f"Blog generation error: {e}")
            return JsonResponse({'error': 'Failed to generate blog article'}, status=500)

        # Save blog article to the database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        # Return blog content as a response
        return JsonResponse({'content': blog_content})

    return JsonResponse({'error': 'Invalid request method'}, status=405)


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
