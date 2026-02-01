import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.ai.prompt import get_suggestion_prompt
from app.auth.token_manager import get_current_user
from app.db.queries import log_llm_call
from app.services.llm_chat import chat_with_deepseek

router = APIRouter(prefix="/ai", tags=["AI"])

class InputPurpose(BaseModel):
    fieldName: str
    inputType: str
    whatIsThisInputFor: str

class PageContext(BaseModel):
    page: str
    pageType: str
    url: str

class SurroundingContext(BaseModel):
    label: str
    textAboveInput: str
    textBelowInput: str
    sectionTitle: str
    whatIsThisAbout: str
    mainContent: str

class SuggestionRequest(BaseModel):
    userInput: str
    userPrompt: str
    inputPurpose: InputPurpose
    pageContext: PageContext
    surroundingContext: SurroundingContext

@router.get("/")
async def get_ai():
    return {"message": "Hello, World!"}

@router.post("/suggestions")
async def get_suggestions(request: SuggestionRequest, user=Depends(get_current_user)):
    """
    Generate text completion suggestions based on user input and context.
    Requires Bearer token; user_id from JWT is used for logging.
    """

    print(user)
    try:
        # Generate the prompt using the prompt function
        prompt = get_suggestion_prompt(
            user_input=request.userInput,
            user_prompt=request.userPrompt,
            field_name=request.inputPurpose.fieldName,
            input_type=request.inputPurpose.inputType,
            input_purpose=request.inputPurpose.whatIsThisInputFor,
            page_title=request.pageContext.page,
            page_type=request.pageContext.pageType,
            page_url=request.pageContext.url,
            label=request.surroundingContext.label,
            text_above=request.surroundingContext.textAboveInput,
            text_below=request.surroundingContext.textBelowInput,
            section_title=request.surroundingContext.sectionTitle,
            context_about=request.surroundingContext.whatIsThisAbout,
            main_content=request.surroundingContext.mainContent
        )
        
        # Prepare messages for LLM
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Call the LLM service
        response = chat_with_deepseek(messages, text_only=True)

        # Check if response is an error
        if isinstance(response, str) and response.startswith("Error"):
            raise HTTPException(status_code=500, detail=response)

        # Log LLM call (user_id from JWT Bearer; only if sub is our internal id, fits bigint)
        if isinstance(response, dict) and response.get("usage"):
            usage = response["usage"]
            try:
                uid = int(user["sub"])
                if -(2**63) <= uid <= 2**63 - 1:  # PostgreSQL bigint range
                    log_llm_call(
                        model=response.get("model", ""),
                        tokens_in=usage.get("prompt_tokens", 0),
                        tokens_out=usage.get("completion_tokens", 0),
                        cost=float(usage.get("estimated_cost", 0) or 0),
                        user_id=uid,
                    )
            except (ValueError, TypeError):
                pass  # sub not an int (e.g. Google id string); skip logging

        # Extract the content from response
        llm_content = response.get("data", "") if isinstance(response, dict) else str(response)
        
        # Try to parse JSON from the response
        # Remove markdown code blocks if present
        content = llm_content.strip()
        if content.startswith("```"):
            # Remove markdown code blocks
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
        
        # Parse JSON
        try:
            suggestions_data = json.loads(content)
            return suggestions_data
        except json.JSONDecodeError:
            # If JSON parsing fails, return the raw response
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse LLM response as JSON: {content[:200]}"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

