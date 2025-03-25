from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from typing import Optional, List, Dict, Any
import uvicorn
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(
    title="YouTube Chapter Generator API",
    description="API to generate chapter timestamps for YouTube videos",
    version="0.1.0"
)

# Pydantic model for request validation
class VideoRequest(BaseModel):
    url: str
    language: Optional[str] = None  # Now optional
    
# Pydantic model for chapter format
class Chapter(BaseModel):
    timestamp: str
    title: str

# Function to extract video ID from URL
def extract_video_id(url: str) -> str:
    """
    Extracts the video ID from a YouTube URL.
    """
    if 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    else:
        raise ValueError("Invalid YouTube URL")

# Function to format time from seconds to MM:SS
def format_time(seconds: float) -> str:
    """
    Converts time from seconds (float) to MM:SS format.
    """
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02}:{seconds:02}"  # Ensures two-digit formatting

# Function to fetch transcript
def fetch_transcript(video_url: str, language_code: str = None):
    """
    Fetches the transcript for a YouTube video.
    Automatically detects the best available language if not specified.
    """
    try:
        video_id = extract_video_id(video_url)
        
        # Get available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Auto-detect language if not provided
        if not language_code:
            # Prioritize English if available
            if 'en' in [t.language_code for t in transcript_list]:
                language_code = 'en'
            else:
                # Fall back to the first available language
                language_code = next(iter(transcript_list)).language_code

        # Fetch the transcript in the detected language
        transcript = transcript_list.find_transcript([language_code]).fetch()

        # Format transcript with MM:SS timestamps
        formatted_transcript = [
            {
                "time": format_time(entry['start']),
                "text": entry['text'],
                "start": entry['start'],
                "duration": entry['duration']
            }
            for entry in transcript
        ]

        return formatted_transcript, language_code

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Error fetching transcript: {str(e)}")


# Function to generate initial chapters using Gemini AI
async def generate_chapters_with_gemini(transcript: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Uses Gemini AI to generate chapter timestamps and titles from a transcript.
    
    Args:
        transcript: The formatted transcript with timestamps and text
        
    Returns:
        A list of chapters with timestamps and titles
    """
    try:
        # Configure the model
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",  # Using a valid model name
            generation_config={
                "temperature": 0.3,
                "top_p": 0.95,
                "top_k": 40,
            }
        )
        
        # Format transcript with timestamps for the AI
        transcript_with_timestamps = "\n".join([f"[{entry['time']}] {entry['text']}" for entry in transcript])
        
        # Create the prompt for Gemini (keeping your existing prompt)
        prompt = f"""
        You are a video summarization assistant that generates clear and concise chapter timestamps for YouTube videos. Your goal is to analyze a provided transcript and the total video duration, and then identify only the major segments of the video in a balanced way. Follow these instructions exactly:
        1. Input Details:
        - You will receive the full transcript of a YouTube video along with its total duration (e.g., 20:00).
        - If the transcript is in a non-English language, first translate it to English before processing.
        2. Chapter Creation:
        - Identify only significant topic shifts or major modules that represent a clear, substantial change in content.
        - Avoid creating chapters for minor transitions or repetitive content. Group similar or consecutive content into one chapter.
        - Generate a balanced number of chapters relative to the video length. For a 20-minute video, aim for between 5 to 8 chapters.
        - Ensure chapters are evenly distributed across the entire video duration so that early, middle, and later segments are all represented.
        - Do not create any chapter timestamps beyond the total video duration. All timestamps must be within the video's length.
        3. Timestamp and Output Format:
        - Each chapter must include:
            - An approximate timestamp in the format MM:SS (e.g., 03:15) that reflects the start time of that major segment.
            - A brief, descriptive title summarizing the key topic of that segment.
        - List the chapters in sequential order with clearly formatted timestamps (MM:SS).
        4. Additional Guidelines:
        - Ensure the final chapter reflects the concluding segment of the video, and do not extend beyond the video's total duration.
        - Focus on capturing only the essential highlights and avoid over-fragmentation.
        - Provide a final, easy-to-follow list of chapters that covers the entire video in a balanced manner.

        Using these guidelines, generate a set of chapters that accurately represents the key points in the transcript without exceeding the video's actual length.
        
        TRANSCRIPT WITH TIMESTAMPS:
        {transcript_with_timestamps}  # Limiting transcript length to avoid token limits
        
        OUTPUT FORMAT (ONLY):
        00:00 - Introduction
        MM:SS - Chapter Title
        MM:SS - Chapter Title
        ...
        """
        
        # Generate response from Gemini
        response = model.generate_content(prompt)
        
        # Parse the response to extract chapters
        chapters_text = response.text.strip().split('\n')
        chapters = []
        
        for chapter in chapters_text:
            if ' - ' in chapter and ':' in chapter.split(' - ')[0]:
                parts = chapter.split(' - ', 1)
                timestamp = parts[0].strip()
                title = parts[1].strip()
                chapters.append({"timestamp": timestamp, "title": title})
        
        return chapters
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating chapters with AI: {str(e)}")

# Function to refine chapters using Gemini AI
async def refine_chapters_with_gemini(initial_chapters: List[Dict[str, str]], transcript: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Uses Gemini AI to refine the initial chapters by analyzing them alongside the transcript.
    
    Args:
        initial_chapters: The initial chapters generated in the first pass
        transcript: The formatted transcript with timestamps and text
        
    Returns:
        A refined list of chapters with timestamps and titles
    """
    try:
        # Configure the model
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={
                "temperature": 0.1,  # Lower temperature for more precise refinement
                "top_p": 0.95,
                "top_k": 40,
            }
        )
        
        # Format transcript with timestamps for the AI
        transcript_with_timestamps = "\n".join([f"[{entry['time']}] {entry['text']}" for entry in transcript])
        
        # Format initial chapters for the AI
        initial_chapters_formatted = "\n".join([f"{chapter['timestamp']} - {chapter['title']}" for chapter in initial_chapters])
        
        # Create the prompt for Gemini refinement
        prompt = f"""
        You are an advanced video summarization assistant specializing in refining chapter timestamps for YouTube videos. Your task is to take the preliminary chapter/timestamp list (generated by another AI) along with the complete transcript of the video, and produce a final, optimized set of chapters. Follow these guidelines:
        1. Input:
        - You will receive the initial chapters and timestamps (in MM:SS format) that were generated.
        - You will also receive the full transcript of the video.
        - If the transcript is in a non-English language, first translate it to English before processing.
        2. Analysis and Comparison:
        - Analyze the preliminary chapter list in the context of the transcript.
        - Identify and remove any chapters that are unnecessary, redundant, or overly granular.
        - Merge chapters that cover similar or consecutive topics, ensuring that each chapter reflects a significant topic shift.
        - Ensure that the chapters cover the entire video and are evenly distributed.
        3. Final Chapter Generation:
        - Generate a final set of chapters with timestamps in MM:SS format that represent the major segments of the video.
        - For a 20-minute video, aim for a balanced number of chapters (typically between 5 to 8).
        - Ensure no chapter timestamp extends beyond the total video duration.
        - Provide concise and descriptive titles for each chapter that clearly summarize the segment's content.
        4. Output:
        - Present the final chapter list in sequential order with each chapter's timestamp and title.
        - The final list should be clear, balanced, and easy for viewers to navigate.

        Using these guidelines, generate the final, optimized set of chapters and timestamps that best represent the video content.        
        INITIAL CHAPTERS:
        {initial_chapters_formatted}
        
        TRANSCRIPT WITH TIMESTAMPS:
        {transcript_with_timestamps}
        
        OUTPUT FORMAT (ONLY):
        00:00 - Introduction
        MM:SS - Chapter Title
        MM:SS - Chapter Title
        ...
        """
        
        # Generate response from Gemini
        response = model.generate_content(prompt)
        
        # Parse the response to extract refined chapters
        refined_chapters_text = response.text.strip().split('\n')
        refined_chapters = []
        
        for chapter in refined_chapters_text:
            if ' - ' in chapter and ':' in chapter.split(' - ')[0]:
                parts = chapter.split(' - ', 1)
                timestamp = parts[0].strip()
                title = parts[1].strip()
                refined_chapters.append({"timestamp": timestamp, "title": title})
        
        return refined_chapters
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error refining chapters with AI: {str(e)}")

@app.post("/generate_chapters")
async def generate_chapters(request: VideoRequest):
    """
    Endpoint to generate chapter timestamps for a YouTube video using Gemini AI.
    """
    try:
        # Extract transcript with automatic language detection if not specified
        transcript, detected_language = fetch_transcript(request.url, request.language)
        
        # Concatenate transcript segments into a text string (for reference)
        full_text = " ".join([entry["text"] for entry in transcript])
        
        try:
            # Generate initial chapters using Gemini AI with the full transcript including timestamps
            initial_chapters = await generate_chapters_with_gemini(transcript)
            
            # Refine the chapters using a second pass
            refined_chapters = await refine_chapters_with_gemini(initial_chapters, transcript)
            
            return {
                "success": True,
                "video_id": extract_video_id(request.url),
                "language": detected_language,
                "transcript": transcript,
                "full_text": full_text,
                "initial_chapters": initial_chapters,
                "chapters": refined_chapters  # Return the refined chapters as the main result
            }
        except Exception as ai_error:
            # Provide detailed error about AI processing
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error processing with AI: {str(ai_error)}")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/")
async def root():
    return {"message": "YouTube Chapter Generator API is running. Use /generate_chapters endpoint to extract transcripts."}
