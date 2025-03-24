import streamlit as st
import numpy as np
import streamlit.components.v1 as components

st.title("Data Visualization web application")
#st.header("Part 1: Data Exploration")
#st.write("In this section, we will explore the Altair cars dataset.")
#st.markdown("*Further resources [here](https://altair-viz.github.io/gallery/selection_histogram.html)*")


with st.container():
    #st.write("This is inside the container")

    # You can call any Streamlit command, including custom components:
    st.bar_chart(np.random.randn(50, 3))

st.write("This is outside the container")

# The Google Looker Studio embed URL
looker_studio_url = "https://lookerstudio.google.com/embed/reporting/2d7a0e27-262c-410e-b077-5a5c3f21ea9f/page/5JCAF"
components.iframe(looker_studio_url, width=600 , height=450)