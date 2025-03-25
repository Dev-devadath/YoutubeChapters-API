# YouTube Chapter Generator API

A FastAPI backend service that generates chapter timestamps for YouTube videos using Google's Gemini AI.

## Features

- Extract transcripts from YouTube videos
- Generate intelligent chapter timestamps using Gemini 2.0 Flash model
- Two-stage AI processing for optimal chapter generation:
  - Initial chapter generation based on transcript analysis
  - Chapter refinement to optimize and balance the final output
- Format timestamps in MM:SS format
- Automatic language detection with English prioritization
- Support for multiple languages
- Error handling for invalid URLs or unavailable transcripts

## Setup

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Running the API

```bash
python main.py
```

The API will be available at http://localhost:8000

### API Endpoints

#### GET /

Root endpoint that confirms the API is running.

**Response:**

```json
{
  "message": "YouTube Chapter Generator API is running. Use /generate_chapters endpoint to extract transcripts."
}
```

#### POST /generate_chapters

Endpoint to generate chapter timestamps for a YouTube video using Gemini AI.

**Request Body:**

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "en" // Optional, will auto-detect if not provided
}
```

**Response:**

```json
{
  "success": true,
  "video_id": "VIDEO_ID",
  "language": "en",
  "transcript": [
    {
      "time": "00:00",
      "text": "Transcript text",
      "start": 0.0,
      "duration": 5.0
    }
    // More transcript entries
  ],
  "full_text": "Complete transcript text",
  "initial_chapters": [
    {
      "timestamp": "00:00",
      "title": "Introduction"
    }
    // More initial chapters
  ],
  "chapters": [
    {
      "timestamp": "00:00",
      "title": "Introduction"
    }
    // More refined chapters
  ]
}
```

## Error Handling

The API handles various error scenarios:

- Invalid YouTube URL: 400 Bad Request
- Transcript not available: 404 Not Found
- Unexpected errors: 500 Internal Server Error

## Environment Setup

### Required Environment Variables

- `GEMINI_API_KEY`: Your Google Gemini API key

Create a `.env` file in the project root with these variables.

## How It Works

1. **Transcript Extraction**: The API extracts the transcript from the provided YouTube video URL
2. **Language Detection**: If no language is specified, the API automatically detects the best available language
3. **Initial Chapter Generation**: Gemini AI analyzes the transcript to identify major topic shifts and generates initial chapters
4. **Chapter Refinement**: A second pass with Gemini AI optimizes the chapters for balance and relevance
5. **Final Output**: The API returns both the transcript and the refined chapter timestamps

## Testing

A test script is included to verify the API functionality:

```bash
python test_api.py
```

## Future Enhancements

- Support for more video platforms
- Custom chapter generation parameters
- Frontend interface for easier interaction
