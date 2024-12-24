MEMORY_EXTRACTION_SYSTEM_PROMPT = """
The Current Date & Time is {day_of_week}, {current_datetime_str}.
Given an interaction between ({agent_label}) and ({user_name}).

# OBJECTIVE: 
- Extract details about {user_name} {extract_for_agent} from the interaction to be stored in memory used to personalize future interactions.
- Ignore insignificant details that you are very certain will be unhelpful in future personalized responses.
- Never fabricate any detail not present or strongly implied in the interaction.

# MEMORY GUIDELINES:  
- Keep each memory descriptive, self-contained, not exceed 25 words.  
- Use proper tense (past, present, continuous) as appropriate.  
- Always use #user_#id# instead of ({user_name}) and #agent_#id# instead of ({agent_label}) in the memories. 
- Output must be JSON format using the schema:
{schema}


>>>>>>> ENTIRE INTERACTION IS BELOW <<<<<<<
"""

COMPARE_EXISTING_AND_NEW_MEMORIES_SYSTEM_PROMPT = """
The Current Date & Time is {day_of_week}, {current_datetime_str}.

You manage memories for {user_placeholder} / {agent_placeholder}.  
You are given existing stored memories and candidate new memories.  

# Objective: 
1. Identify New Memories:
   - Information gleaned from candidate memories that are not updates to any existing memory.

2. Identify Contradictory Memories:
   - Candidate memories that directly contradict existing stored memories.


# IMPORTANT GUIDELINES
- DO NOT GIVE ANY EXPLANATIONS.
- The Output JSON object must use the schema: {schema}

"""

COMPARE_EXISTING_AND_NEW_MEMORIES_PROMPT_TEMPLATE = """
====
EXISTING MEMORIES 
====

{existing_memories_string}

====  
NEW CANDIDATE MEMORIES  
====  

{new_memories_string}

"""