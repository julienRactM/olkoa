"""
Email viewer component for the Okloa project.

This module provides functions for displaying email content in different formats.
"""

import streamlit as st
import pandas as pd
from typing import Callable, Dict, Any, List, Optional
import os
import sys
import json
from streamlit_modal import Modal

# Add the project root to the path so we can import constants
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Try to import constants, with a fallback for testing
try:
    from constants import EMAIL_DISPLAY_TYPE
except ImportError:
    # Default for testing
    EMAIL_DISPLAY_TYPE = "MODAL"

# CSS for the email display
EMAIL_STYLE_CSS = """
<style>
/* Better styling for standard Streamlit tables */
div[data-testid="stTable"] table {
    width: 100%;
}
div[data-testid="stTable"] th {
    background-color: #f0f0f0;
    font-weight: bold;
}
div[data-testid="stTable"] tr:hover {
    background-color: #f0f8ff;
}

/* Email header styling */
.email-header {
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid #eee;
}

/* Email content styling */
.email-content {
    white-space: pre-line;
    font-family: Arial, sans-serif;
    line-height: 1.5;
}
</style>
"""

def format_email_date(date_obj):
    """Format a datetime object for display."""
    if pd.isna(date_obj):
        return ""
    return date_obj.strftime('%Y-%m-%d %H:%M')

def create_email_table_with_viewer(
    emails_df: pd.DataFrame,
    key_prefix: str = "email_table"
) -> None:
    """
    Create an interactive email table with content viewer.
    
    Args:
        emails_df: DataFrame containing email data
        key_prefix: Prefix for Streamlit keys to avoid conflicts
        
    Returns:
        None
    """
    if emails_df.empty:
        st.info("Aucun email à afficher.")
        return
    
    # Create a copy with limited columns for display
    display_df = emails_df[['date', 'from', 'to', 'subject']].copy()
    
    # Format date for display
    if 'date' in display_df.columns:
        display_df['date'] = display_df['date'].apply(format_email_date)
    
    if EMAIL_DISPLAY_TYPE == "POPOVER":
        _create_popover_email_table(emails_df, display_df, key_prefix)
    else:  # Default to MODAL
        _create_modal_email_table(emails_df, display_df, key_prefix)

def _create_popover_email_table(
    emails_df: pd.DataFrame,
    display_df: pd.DataFrame,
    key_prefix: str
) -> None:
    """Create an email table with popover display on hover."""
    st.write("Popover not implemented in this version.")
    # Implementation would go here if needed

def _create_modal_email_table(
    emails_df: pd.DataFrame,
    display_df: pd.DataFrame,
    key_prefix: str
) -> None:
    """Create an email table with a modal using streamlit_modal library when clicked."""
    
    # Add an internal index column to track selections
    display_df = display_df.copy()
    display_df['_index'] = list(range(len(display_df)))
    
    # Initialize session state variables if not exists
    selected_email_key = f"{key_prefix}_selected_idx"
    if selected_email_key not in st.session_state:
        st.session_state[selected_email_key] = None
    
    # Inject CSS for styling the table
    st.markdown(EMAIL_STYLE_CSS, unsafe_allow_html=True)
    
    # Display the standard Streamlit table
    st.caption("Utilisez le sélecteur ci-dessous pour voir le contenu d'un email")
    
    # Display simple table using standard Streamlit dataframe
    st.dataframe(
        display_df[['date', 'from', 'to', 'subject']],
        hide_index=True,
        use_container_width=True,
        key=f"{key_prefix}_table"
    )
    
    # Provide a selectbox option for selecting emails
    cols = st.columns([3, 1])
    with cols[0]:
        selected_idx = st.selectbox(
            "Sélectionnez un email à afficher",
            options=list(range(len(display_df))),
            format_func=lambda i: f"{display_df.iloc[i]['date']} - {display_df.iloc[i]['subject'][:40]}...",
            key=f"{key_prefix}_select"
        )
    
    with cols[1]:
        # Button to view the selected email
        if st.button("Voir le contenu", key=f"{key_prefix}_view_btn"):
            st.session_state[selected_email_key] = selected_idx
    
    # Show email content in a modal if an email is selected
    if st.session_state[selected_email_key] is not None:
        # Get the index of the person whose details should be shown
        selected_idx = st.session_state[selected_email_key]
        
        # Make sure the index is valid
        if 0 <= selected_idx < len(emails_df):
            selected_email = emails_df.iloc[selected_idx]
            
            # Create and configure the Modal
            modal = Modal(
                title=f"Email: {selected_email['subject'][:100]}",
                key=f"{key_prefix}_email_modal_{selected_idx}"
            )
            
            # Modal content
            with modal.container():
                # Email metadata
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**De:** {selected_email['from']}")
                    st.markdown(f"**À:** {selected_email['to']}")
                
                with col2:
                    st.markdown(f"**Date:** {format_email_date(selected_email['date'])}")
                    if selected_email.get('has_attachments'):
                        st.markdown(f"**Pièces jointes:** {selected_email['attachments']}")
                
                # Email body
                st.markdown("---")
                st.text_area(
                    "Contenu de l'email", 
                    value=selected_email['body'], 
                    height=400,
                    disabled=True
                )
                
                # Close button
                if st.button("Fermer", key=f"{key_prefix}_close_btn_{selected_idx}"):
                    st.session_state[selected_email_key] = None
                    st.rerun()
        else:
            # Invalid index
            st.error(f"Index invalide: {selected_idx}")
            st.session_state[selected_email_key] = None

if __name__ == "__main__":
    # Test code - this will run when the module is executed directly
    st.title("Email Viewer Test")
    
    # Create sample data
    data = {
        "date": [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")],
        "from": ["sender1@example.com", "sender2@example.com"],
        "to": ["recipient1@example.com", "recipient2@example.com"],
        "subject": ["Test Subject 1", "Test Subject 2"],
        "body": ["This is the body of email 1", "This is the body of email 2"],
        "has_attachments": [False, True],
        "attachments": ["", "file.pdf"]
    }
    
    df = pd.DataFrame(data)
    
    # Display the table
    create_email_table_with_viewer(df)
