import openai
import streamlit as st
from fpdf import FPDF
import base64

# Set your OpenAI API key
openai.api_key = ''
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
        max_tokens=900,  # Adjusted to allow for a longer response
        temperature=0.7,
    )
    
    story = response.choices[0].message['content'].strip()
    return story

def convert_to_pdf(story_parts):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    for part in story_parts:
        pdf.multi_cell(0, 10, part)

    return pdf

def main():
    st.title("Interactive Storytelling App")
    
    if "story" not in st.session_state:
        st.session_state.story = []
        st.session_state.started = False
        st.session_state.stopped = False

    if not st.session_state.started:
        st.write("Enter the base story idea to start your interactive story.")
        base_story = st.text_area("Base Story Idea", height=150)
        if st.button("Start Story"):
            if base_story.strip():
                st.session_state.story.append(base_story)
                st.session_state.started = True
                st.write(base_story)
            else:
                st.warning("Please enter a base story idea to start.")
    else:
        # Display the current story
        for part in st.session_state.story:
            st.write(part)
        
        if not st.session_state.stopped:
            user_choice = st.text_input("What does Alex do next?")

            if st.button("Continue Story"):
                if user_choice:
                    new_story = generate_story(" ".join(st.session_state.story), user_choice)
                    st.session_state.story.append(new_story)
                    st.write(new_story)
                else:
                    st.warning("Please enter a choice to continue the story.")
            
            if st.button("Continue Automatically"):
                last_part = st.session_state.story[-1] if st.session_state.story else ""
                new_story = generate_story(" ".join(st.session_state.story), last_part)
                st.session_state.story.append(new_story)
                st.write(new_story)
            
            if st.button("Stop Story"):
                st.session_state.stopped = True
        
        if st.session_state.stopped:
            if st.button("Convert to PDF"):
                pdf = convert_to_pdf(st.session_state.story)
                pdf_output = pdf.output(dest='S').encode('latin1')
                b64_pdf = base64.b64encode(pdf_output).decode('latin1')
                href = f'<a href="data:application/octet-stream;base64,{b64_pdf}" download="story.pdf">Download PDF</a>'
                st.markdown(href, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
