import os
import json
import re
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.conf import settings
import random
import google.generativeai as genai
from .models import BlogPost
from django_ratelimit.decorators import ratelimit

logger = logging.getLogger('blog_generator')

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


# Build proxy list from env vars at startup (PROXY_1=http://..., PROXY_2=http://...)
proxies_list = [v for k, v in os.environ.items() if k.startswith("PROXY_")]


def _get_proxy_dict() -> dict | None:
    """Return a random proxy dict for requests, or None if no proxies configured."""
    if not proxies_list:
        return None
    proxy = random.choice(proxies_list)
    return {"http": proxy, "https": proxy}


def fetch_transcript(video_id: str, languages=['en', 'mr', 'hi']) -> str:
    """
    Fetch YouTube transcript via youtube-transcript-api.

    Passes proxies directly to the YouTubeTranscriptApi constructor — the only
    correct way. The old approach of monkey-patching requests.get did NOT work
    because the library uses requests.Session internally, not requests.get.

    Production note: YouTube blocks datacenter IPs (Railway, Render, AWS, etc).
    Set PROXY_1, PROXY_2, ... env vars to residential proxy URLs to bypass this.
    """
    try:
        proxies = _get_proxy_dict()
        ytt_api = YouTubeTranscriptApi(proxies=proxies) if proxies else YouTubeTranscriptApi()
        fetched_transcript = ytt_api.fetch(video_id, languages=languages)
        return " ".join([snippet.text for snippet in fetched_transcript])
    except Exception as e:
        logger.error(f"Transcript fetch error for video {video_id}: {e}")
        return None




def generate_blog_from_transcription(transcription: str) -> str:
    """
    Generate a blog or appropriate summary from a YouTube transcript using Gemini API.
    Intelligently adapts to different video types (educational, music, sports, etc).
    Title is provided by the user, so this only returns blog/summary content.
    """

    prompt = f"""
    You are an expert content creator and formatter.
    
    Your task: Analyze the video transcript and generate appropriate content based on video type.
    
    ## Step 1: Detect Video Type
    Determine what type of video this is:
    - **Educational/Tutorial**: Coding, how-to, tips, explanations, courses
    - **Tech/Product Review**: Reviews, comparisons, analysis
    - **Documentary/Interview**: Deep dives, interviews, discussions
    - **Lifestyle/General**: Vlogs, personal content, storytelling
    - **Music**: Songs, music videos, albums, covers
    - **Sports**: Matches, highlights, sports analysis
    - **Entertainment**: Comedy, pranks, short-form content
    - **Other**: Anything else
    
    ## Step 2: Generate Content Based on Type
    
    ### FOR EDUCATIONAL/TUTORIAL/TECH/DOCUMENTARY:
    Structure as a **professional blog post** with:
    
    ## Introduction
    - Hook the reader with why this matters
    - Brief overview of what they'll learn
    
    ## Key Concepts
    - Main ideas or topics covered
    - Use bullet points with clear explanations
    
    ## Deep Dive
    - Detailed sections with H3 subheadings
    - Practical examples, tips, or best practices
    
    ## Key Takeaways
    - Summarize actionable insights
    - Suggest next steps
    
    ### FOR MUSIC/ENTERTAINMENT:
    Create a **summary/review** with:
    
    ## Overview
    - Title, Artist(s), Genre (if mentioned)
    - Key themes and mood
    
    ## Content Summary
    - Main story, lyrics theme, or message
    - Notable moments or sections
    
    ## Impressions
    - Standout elements
    - Overall vibe and appeal
    
    ### FOR SPORTS:
    Create a **match/event summary** with:
    
    ## Match Overview
    - Teams/Players, Date, Final Result
    
    ## Key Moments
    - Turning points and highlights
    - Notable performances
    
    ## Analysis
    - What went well, what changed
    
    ### FOR OTHER TYPES:
    Create a **brief, engaging summary** (5-7 short sections max)
    
    ## Formatting Rules (ALL types):
    - Use H2 for main sections (## Section)
    - Use H3 for subsections (### Subsection)
    - Use **bold** for important terms
    - Use bullet points or numbered lists
    - Use > for blockquotes or highlights
    - Keep language clear and conversational
    - Aim for 500-1500 words depending on content
    
    ## Critical Output Rules:
    - Return ONLY the formatted content
    - DO NOT include a title (user provides it)
    - DO NOT include meta information
    - DO NOT add disclaimers or notes
    - DO NOT say "This is a music video" or similar explanations
    - Start directly with the first H2 heading
    
    ## Video Transcript:
    {transcription}
    
    Generate the content now following the appropriate structure for the video type detected.
    """

    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    blog_text = response.text.strip()

    return blog_text


def format_blog_content(raw_content: str) -> str:
    """
    Convert markdown to clean HTML for proper display.
    Handles headers, bold text, lists, code blocks, line breaks naturally.
    """
    formatted = raw_content.strip()
    
    # Normalize line breaks
    formatted = formatted.replace('\r\n', '\n')
    
    # Remove excessive blank lines (keep max 2)
    formatted = re.sub(r'\n{3,}', '\n\n', formatted)
    
    # Convert code blocks FIRST (before inline code): ```language\ncode\n``` to <pre><code>
    # This handles multi-line code blocks with optional language
    def replace_code_block(match):
        language = match.group(1) or ''
        code = match.group(2).strip()
        lang_class = f' class="language-{language}"' if language else ''
        return f'<pre><code{lang_class}>{code}</code></pre>'
    
    formatted = re.sub(r'```(\w+)?\n(.*?)```', replace_code_block, formatted, flags=re.DOTALL)
    
    # Convert headers: ## to <h2>, ### to <h3>, etc.
    formatted = re.sub(r'^#### (.*?)$', r'<h4>\1</h4>', formatted, flags=re.MULTILINE)
    formatted = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', formatted, flags=re.MULTILINE)
    formatted = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', formatted, flags=re.MULTILINE)
    formatted = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', formatted, flags=re.MULTILINE)
    
    # Convert bold: **text** to <strong>text</strong>
    formatted = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted)
    
    # Convert italic: *text* to <em>text</em> (but not in bold patterns)
    formatted = re.sub(r'(?<!\*)\*(.*?)\*(?!\*)', r'<em>\1</em>', formatted)
    
    # Convert inline code: `code` to <code>code</code> (but not already in <pre><code>)
    formatted = re.sub(r'(?<!<code>)`([^`]+)`(?!</code>)', r'<code>\1</code>', formatted)
    
    # Convert bullet points: - item or * item to <li>item</li>
    lines = formatted.split('\n')
    result = []
    in_list = False
    
    for line in lines:
        if re.match(r'^[\s]*[-*]\s+', line):
            if not in_list:
                result.append('<ul>')
                in_list = True
            # Remove the bullet and add as list item
            item = re.sub(r'^[\s]*[-*]\s+', '', line)
            result.append(f'<li>{item}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            if line.strip():  # Only add non-empty lines
                result.append(f'<p>{line}</p>')
            elif line.strip() == '':  # Preserve some spacing
                result.append('')
    
    if in_list:
        result.append('</ul>')
    
    formatted = '\n'.join(result)
    
    # Clean up multiple <p></p> tags
    formatted = re.sub(r'</p>\s*<p>', '</p><p>', formatted)
    
    return formatted

# View Functions
@login_required
def index(request):
    """Render the index page."""
    return render(request, 'index.html')

def home(request):
    """Render the home page."""
    return render(request, 'home.html')


@login_required
@ratelimit(key='user', rate='1/5m', block=False)
def generate_blog(request):
    """
    Accepts the YouTube link + title, creates a BlogPost with status='pending',
    then dispatches a Celery background task and returns the blog_id immediately.
    The frontend polls /blog-status/<blog_id> to track progress.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    if getattr(request, 'limited', False):
        return JsonResponse(
            {'error': 'Too many requests. Please try again in 5 minutes.'},
            status=429,
            headers={'Retry-After': '300'},
        )

    try:
        data = json.loads(request.body)
        yt_link = data.get('link')
        user_title = data.get('title')

        if not yt_link or not user_title:
            return JsonResponse({'error': 'Both YouTube link and Title are required'}, status=400)

        if not validate_and_extract_video_id(yt_link):
            return JsonResponse({'error': 'Invalid YouTube link'}, status=400)

        # Create the BlogPost immediately (status=pending) so we have an ID to track
        blog = BlogPost.objects.create(
            user=request.user,
            youtube_title=user_title,
            youtube_link=yt_link,
        )

        # Dispatch the heavy work to Celery — returns instantly
        from .tasks import generate_blog_task
        generate_blog_task.delay(blog.id)

        return JsonResponse({'blog_id': blog.id, 'title': user_title}, status=202)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@login_required
def blog_status(request, pk):
    """
    Polling endpoint. Frontend calls this every 2s to check if the background
    task has finished.

    Returns:
      { status: 'pending'|'processing'|'completed'|'failed',
        content: '<html>...',   # only when completed
        error:   '...' }        # only when failed
    """
    try:
        blog = BlogPost.objects.get(id=pk, user=request.user)
    except BlogPost.DoesNotExist:
        return JsonResponse({'error': 'Blog not found'}, status=404)

    response = {'status': blog.status}

    if blog.status == BlogPost.STATUS_COMPLETED:
        response['content'] = blog.generated_content
        response['title'] = blog.youtube_title

    elif blog.status == BlogPost.STATUS_FAILED:
        response['error'] = blog.error_message or 'Generation failed. Please try again.'

    return JsonResponse(response)


@login_required
def blog_list(request):
    """Display all blogs for the logged-in user."""
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})


@login_required
def blog_details(request, pk):
    """Display details of a specific blog."""
    try:
        blog_article_detail = BlogPost.objects.get(id=pk, user=request.user)
    except BlogPost.DoesNotExist:
        return redirect('blog-list')

    content = blog_article_detail.generated_content
    if content and not ('<h2>' in content or '<p>' in content or '<pre>' in content):
        content = format_blog_content(content)

    return render(request, 'blog-details.html', {
        'blog_article_detail': blog_article_detail,
        'formatted_content': content
    })

@login_required
def delete_blog(request, pk):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    try:
        blog = BlogPost.objects.get(id=pk, user=request.user)
        blog.delete()
        return JsonResponse({'success': True})
    except BlogPost.DoesNotExist:
        return JsonResponse({'error': 'Blog not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def user_login(request):
    """Handle user login."""
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('index')
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
                return redirect('index')
            except:
                error_message = "Error occurred, make unique entries"
                return render(request, 'signup.html', {'error_message': error_message})

        error_message = "Passwords do not match"
        return render(request, 'signup.html', {'error_message': error_message})

    return render(request, 'signup.html')


def user_logout(request):
    """Handle user logout."""
    logout(request)
    return redirect('home')
