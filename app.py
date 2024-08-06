import openai
import streamlit as st

# Set your OpenAI API key
openai.api_key = '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'

# Define the prompt template for story generation
prompt_template = """
You are the narrator of an interactive story. The story starts with:

{start}

The user makes a choice: {choice}

Based on this choice, continue the story in a creative way:
"""

def generate_story(prompt, choice):
    # Format the prompt with the initial story and user choice
    formatted_prompt = prompt_template.format(start=prompt, choice=choice)
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": formatted_prompt}
        ],
        max_tokens=150,
        temperature=0.7,
    )
    
    story = response.choices[0].message['content'].strip()
    return story

def main():
    st.title("Interactive Storytelling App")
    
    # Check if 'story' is in session state
    if "story" not in st.session_state:
        st.session_state.story = "Once upon a time in a faraway land, a young hero named Alex embarked on an adventure to find a lost treasure."
    
    # Display the initial or current story
    st.write(st.session_state.story)
    
    user_choice = st.text_input("What does Alex do next?")

    if st.button("Continue Story"):
        if user_choice:
            new_story = generate_story(st.session_state.story, user_choice)
            st.session_state.story = new_story
            st.write(new_story)
        else:
            st.warning("Please enter a choice to continue the story.")
    
    if st.button("Start Over"):
        st.session_state.story = "Once upon a time in a faraway land, a young hero named Alex embarked on an adventure to find a lost treasure."
        st.write(st.session_state.story)

if __name__ == "__main__":
    main()
