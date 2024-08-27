from pytube import YouTube
YouTube('https://youtu.be/0IAPZzGSbME?si=09Q4Cev2GDyyOYeT').streams.first().download()
# yt = YouTube('http://youtube.com/watch?v=2lAe1cqCOXo')
# yt.streams.filter(progressive=True, file_extension='mp4')
#   ... .filter(progressive=True, file_extension='mp4')
#   ... .order_by('resolution')
#   ... .desc()
#   ... .first()
#   ... .download()