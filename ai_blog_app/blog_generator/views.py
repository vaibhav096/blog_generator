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
import requests, random
import google.generativeai as genai
from .models import BlogPost
from django_ratelimit.decorators import ratelimit
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


proxies_list = []
for key, value in os.environ.items():
    if key.startswith("PROXY_"):
        proxies_list.append(value)

# Save original requests.get
old_get = requests.get

# Define a monkey-patched get
def proxy_get(url, *args, **kwargs):
    if proxies_list:
        proxy = random.choice(proxies_list)  # pick a random proxy
        kwargs["proxies"] = {"http": proxy, "https": proxy}
    return old_get(url, *args, **kwargs)

# Patch requests.get globally
requests.get = proxy_get


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
@csrf_exempt
@ratelimit(key='user', rate='1/5m', block=False)
def generate_blog(request):
    """Generate a blog from a YouTube video link (title is user-provided)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    if getattr(request, 'limited', False):
        return JsonResponse({
            'error': 'Too many requests. Please try again in 5 minutes.'
        }, status=429, headers={'Retry-After': '300'})

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
            blog_content_raw = generate_blog_from_transcription(transcription)
            blog_content = format_blog_content(blog_content_raw)  # ✅ apply formatting here
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
        # Format the content if it's not already HTML-formatted
        # Check if content has HTML tags, if not, format it
        content = blog_article_detail.generated_content
        if not ('<h2>' in content or '<p>' in content or '<pre>' in content):
            # Content is raw markdown, format it
            content = format_blog_content(content)
        
        return render(request, 'blog-details.html', {
            'blog_article_detail': blog_article_detail,
            'formatted_content': content
        })
    else:
        return redirect('index')

@csrf_exempt
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
