"""
Okloa - Main Streamlit Application

This is the entry point for the Okloa application, providing an interface
for exploring and analyzing archived email data.
"""

import streamlit as st
import pandas as pd
import os
import sys
import time

# Add the necessary paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')));

# Import project constants and elasticsearch enhanced search functionality
from constants import EMAIL_DISPLAY_TYPE, SIDEBAR_STATE
from src.features.elasticsearch_enhanced import enhanced_search_emails

# Set page configuration - MUST BE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="Okloa - Email Archive Analytics",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state=SIDEBAR_STATE,
)

# Import application components - using relative import
sys.path.append(os.path.dirname(__file__))
from components.email_viewer import create_email_table_with_viewer

from src.data.loading import load_mailboxes
from src.features.embeddings import generate_embeddings
from src.visualization.email_network import create_network_graph
from src.visualization.timeline import create_timeline
from src.rag.initialization import initialize_rag_system
from src.rag.retrieval import get_rag_answer
from src.features.search import search_emails

# Page configuration is already set at the top of the file

# Application title and description
st.title("Okloa - Email Archive Analytics")
st.markdown("""
    Welcome to Okloa, a platform for exploring and analyzing archived email data.
    This application helps you visualize email communication patterns, search through
    the corpus, and extract insights using advanced natural language processing techniques.
""")

# Sidebar for navigation and controls
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select a page:",
    ["Dashboard", "Email Explorer", "Network Analysis", "Timeline", "Recherche", "Recherche ElasticSearch", "Chat"]
)

# Data loading section (in the sidebar)
st.sidebar.title("Data")
mailbox_options = ["All Mailboxes", "Mailbox 1", "Mailbox 2", "Mailbox 3"]
selected_mailbox = st.sidebar.selectbox("Select Mailbox:", mailbox_options)

# Store selected mailbox in session state for other pages to access
st.session_state.selected_mailbox = selected_mailbox

# Timeframe selection
st.sidebar.title("Filters")
date_range = st.sidebar.date_input(
    "Date Range:",
    value=(pd.to_datetime("2023-01-01"), pd.to_datetime("2023-12-31")),
)

# Load data based on selection
@st.cache_data
def load_data(mailbox_selection):
    """Load and cache the selected mailbox data"""
    # Get the project root directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    base_dir = os.path.join(project_root, 'data', 'raw')

    st.sidebar.write(f"Looking for mailboxes in: {base_dir}")

    try:
        if mailbox_selection == "All Mailboxes":
            df = load_mailboxes(["mailbox_1", "mailbox_2", "mailbox_3"], base_dir=base_dir)
        else:
            # Extract the number from the selection
            mailbox_num = mailbox_selection.split()[-1]
            df = load_mailboxes([f"mailbox_{mailbox_num}"], base_dir=base_dir)

        if len(df) == 0:
            st.sidebar.warning("No emails found in the selected mailbox(es).")
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=[
                "message_id", "date", "from", "to", "cc", "subject",
                "body", "attachments", "has_attachments", "direction", "mailbox"
            ])

        return df
    except Exception as e:
        st.sidebar.error(f"Error loading mailboxes: {e}")
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=[
            "message_id", "date", "from", "to", "cc", "subject",
            "body", "attachments", "has_attachments", "direction", "mailbox"
        ])

# Main content
if page == "Dashboard":
    emails_df = load_data(selected_mailbox)

    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Emails", len(emails_df))

    with col2:
        sent_count = len(emails_df[emails_df["direction"] == "sent"])
        st.metric("Sent Emails", sent_count)

    with col3:
        received_count = len(emails_df[emails_df["direction"] == "received"])
        st.metric("Received Emails", received_count)

    with col4:
        unique_contacts = emails_df["from"].nunique() + emails_df["to"].nunique()
        st.metric("Unique Contacts", unique_contacts)

    # Timeline chart
    st.subheader("Email Activity Over Time")
    st.plotly_chart(create_timeline(emails_df), use_container_width=True)

    # Top contacts
    st.subheader("Top Contacts")
    # This would be implemented in a real application

elif page == "Email Explorer":
    emails_df = load_data(selected_mailbox)
    st.subheader("Email Explorer")

    # Email list with filter
    search_term = st.text_input("Search in emails:")

    if search_term:
        filtered_df = emails_df[
            emails_df["subject"].str.contains(search_term, case=False, na=False) |
            emails_df["body"].str.contains(search_term, case=False, na=False)
        ]
    else:
        filtered_df = emails_df

    # Display filtered emails with interactive viewer
    st.write(f"Showing {len(filtered_df)} emails")
    create_email_table_with_viewer(filtered_df, key_prefix="explorer")

elif page == "Network Analysis":
    emails_df = load_data(selected_mailbox)
    st.subheader("Email Network Analysis")

    # Network visualization options
    st.write("This view shows the communication network between email addresses.")

    # Display network graph
    st.plotly_chart(create_network_graph(emails_df), use_container_width=True)

elif page == "Timeline":
    emails_df = load_data(selected_mailbox)
    st.subheader("Email Timeline")

    # Timeline visualization
    st.plotly_chart(create_timeline(emails_df), use_container_width=True)

elif page == "Recherche":
    st.subheader("Recherche avancée")

    # Load emails data
    emails_df = load_data(selected_mailbox)

    # Initialize Elasticsearch (mock mode)
    st.write("Cette interface vous permet de rechercher dans vos archives d'emails avec des filtres avancés.")

    # Create a layout with two columns
    col1, col2 = st.columns([2, 1])

    with col1:
        # Search query input
        search_query = st.text_input("Rechercher dans les emails:", placeholder="Entrez des mots-clés...")

    with col2:
        # Direction filter
        direction_options = ["Tous", "Envoyés", "Reçus"]
        selected_direction = st.selectbox("Direction:", direction_options)

        # Convert selection to filter format
        direction_filter = None
        if selected_direction == "Envoyés":
            direction_filter = "sent"
        elif selected_direction == "Reçus":
            direction_filter = "received"

    # Additional filters in an expander
    with st.expander("Filtres avancés"):
        # Date range filter
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            start_date = st.date_input("Date de début:", value=None)
        with col_date2:
            end_date = st.date_input("Date de fin:", value=None)

        # Sender/recipient filters
        col_from, col_to = st.columns(2)

        # Get unique senders and recipients
        unique_senders = emails_df['from'].dropna().unique().tolist()
        unique_recipients = []
        for recipients in emails_df['to'].dropna():
            for recipient in recipients.split(';'):
                recipient = recipient.strip()
                if recipient and recipient not in unique_recipients:
                    unique_recipients.append(recipient)

        with col_from:
            selected_sender = st.selectbox(
                "Expéditeur:",
                ["Tous"] + sorted(unique_senders)
            )
        with col_to:
            selected_recipient = st.selectbox(
                "Destinataire:",
                ["Tous"] + sorted(unique_recipients)
            )

        # Attachment filter
        has_attachments = st.checkbox("Avec pièces jointes")

    # Prepare search filters
    filters = {}
    if direction_filter:
        filters['direction'] = direction_filter
    if selected_sender != "Tous":
        filters['from'] = selected_sender
    if selected_recipient != "Tous":
        filters['to'] = selected_recipient
    if has_attachments:
        filters['has_attachments'] = True

    # Prepare date range
    date_range = {}
    if start_date:
        date_range['start'] = pd.Timestamp(start_date)
    if end_date:
        # Set to end of day
        end_datetime = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        date_range['end'] = end_datetime

    # Execute search when query is submitted
    if search_query or filters or date_range:
        # Show a spinner during search
        with st.spinner("Recherche en cours..."):
            # Use search functionality
            results_df = search_emails(
                emails_df,
                query=search_query,
                filters=filters,
                date_range=date_range
            )

        # Display results
        st.subheader(f"Résultats: {len(results_df)} emails trouvés")

        # Display results using the interactive viewer
        if not results_df.empty:
            create_email_table_with_viewer(results_df, key_prefix="search")
        else:
            st.info("Aucun résultat trouvé. Essayez d'élargir vos critères de recherche.")

elif page == "Recherche ElasticSearch":
    # Load emails data to make it available in session state
    emails_df = load_data(selected_mailbox)
    st.session_state.emails_df = emails_df
    
    # Direct implementation of ElasticSearch search page 
    st.subheader("Recherche ElasticSearch")
    st.write("Cette interface vous permet de rechercher dans vos archives d'emails en utilisant ElasticSearch.")
    
    # Create tabs for different search modes
    search_tabs = st.tabs([
        "Recherche Simple", 
        "Recherche Avancée",
        "Options"
    ])
    
    with search_tabs[0]:  # Simple Search
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Search query input
            search_query = st.text_input(
                "Rechercher dans les emails:", 
                key="simple_search_query",
                placeholder="Entrez des mots-clés..."
            )
        
        with col2:
            # Search mode selection
            search_mode = st.selectbox(
                "Mode de recherche:",
                options=[
                    "all", 
                    "content_and_title", 
                    "title_only", 
                    "content_only"
                ],
                format_func=lambda x: {
                    "all": "Tous les champs",
                    "content_and_title": "Contenu et Titre",
                    "title_only": "Titre uniquement",
                    "content_only": "Contenu uniquement"
                }.get(x, x),
                key="simple_search_mode"
            )
        
        # Direction filter
        direction_options = ["Tous", "Envoyés", "Reçus"]
        selected_direction = st.selectbox("Direction:", direction_options, key="simple_direction")
        
        # Convert selection to filter format
        direction_filter = None
        if selected_direction == "Envoyés":
            direction_filter = "sent"
        elif selected_direction == "Reçus":
            direction_filter = "received"
        
        # Prepare filters
        filters = {}
        if direction_filter:
            filters["direction"] = direction_filter
        
        # Simple search button
        simple_search_button = st.button("Rechercher", key="simple_search_button")
        
        if simple_search_button:
            if not search_query and not filters:
                st.warning("Veuillez saisir au moins un terme de recherche ou sélectionner un filtre.")
            else:
                # Show a spinner during search
                with st.spinner("Recherche en cours..."):
                    # Get fuzziness from session state or default to AUTO
                    fuzziness = st.session_state.get("fuzziness", "AUTO")
                    
                    # Use enhanced search functionality
                    results_df = enhanced_search_emails(
                        emails_df,
                        query=search_query,
                        search_mode=search_mode,
                        filters=filters,
                        fuzziness=fuzziness,
                        size=100  # Limit to 100 results
                    )
                    
                    # Store results in session state
                    st.session_state["search_results"] = results_df
                    
                    # Display results count
                    st.subheader(f"Résultats: {len(results_df)} emails trouvés")
                    
                    # Display results using the interactive viewer
                    if not results_df.empty:
                        create_email_table_with_viewer(results_df, key_prefix="es_search_simple")
                    else:
                        st.info("Aucun résultat trouvé. Essayez d'élargir vos critères de recherche ou de modifier le niveau de fuzziness.")
    
    with search_tabs[1]:  # Advanced Search
        st.write("Recherche avancée avec plus d'options de filtrage")
        
        # Search query input
        search_query = st.text_input(
            "Rechercher dans les emails:", 
            key="advanced_search_query",
            placeholder="Entrez des mots-clés..."
        )
        
        # Select which fields to search in
        st.write("Champs à inclure dans la recherche:")
        col1, col2 = st.columns(2)
        
        with col1:
            include_subject = st.checkbox("Sujet", value=True, key="include_subject")
            include_body = st.checkbox("Contenu", value=True, key="include_body")
        
        with col2:
            include_from = st.checkbox("Expéditeur", value=False, key="include_from")
            include_to = st.checkbox("Destinataire", value=False, key="include_to")
        
        # Build search fields list
        search_fields = []
        if include_subject:
            search_fields.append("subject")
        if include_body:
            search_fields.append("body")
        if include_from:
            search_fields.extend(["from", "from_name"])
        if include_to:
            search_fields.extend(["to", "to_name"])
        
        # At least one field must be selected
        if not search_fields:
            st.warning("Veuillez sélectionner au moins un champ de recherche.")
            search_fields = ["subject", "body"]
        
        # Additional filters in an expander
        with st.expander("Filtres avancés", expanded=True):
            # Date range filter
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                start_date = st.date_input("Date de début:", value=None, key="advanced_start_date")
            with col_date2:
                end_date = st.date_input("Date de fin:", value=None, key="advanced_end_date")
            
            # Sender/recipient filters
            col_from, col_to = st.columns(2)
            
            # Get unique senders and recipients
            unique_senders = emails_df['from'].dropna().unique().tolist()
            unique_recipients = []
            for recipients in emails_df['to'].dropna():
                for recipient in recipients.split(';'):
                    recipient = recipient.strip()
                    if recipient and recipient not in unique_recipients:
                        unique_recipients.append(recipient)
            
            with col_from:
                selected_sender = st.selectbox(
                    "Expéditeur:",
                    ["Tous"] + sorted(unique_senders),
                    key="advanced_sender"
                )
            with col_to:
                selected_recipient = st.selectbox(
                    "Destinataire:",
                    ["Tous"] + sorted(unique_recipients),
                    key="advanced_recipient"
                )
            
            # Attachment filter
            has_attachments = st.checkbox("Avec pièces jointes", key="advanced_has_attachments")
            
            # Direction filter
            direction_options = ["Tous", "Envoyés", "Reçus"]
            selected_direction = st.selectbox("Direction:", direction_options, key="advanced_direction")
            
            # Convert selection to filter format
            direction_filter = None
            if selected_direction == "Envoyés":
                direction_filter = "sent"
            elif selected_direction == "Reçus":
                direction_filter = "received"
        
        # Prepare search filters
        filters = {}
        if direction_filter:
            filters['direction'] = direction_filter
        if selected_sender != "Tous":
            filters['from'] = selected_sender
        if selected_recipient != "Tous":
            filters['to'] = selected_recipient
        if has_attachments:
            filters['has_attachments'] = True
        
        # Prepare date range
        date_range = {}
        if start_date:
            date_range['start'] = pd.Timestamp(start_date)
        if end_date:
            # Set to end of day
            end_datetime = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            date_range['end'] = end_datetime
        
        # Advanced search button
        advanced_search_button = st.button("Rechercher", key="advanced_search_button")
        
        if advanced_search_button:
            if not search_query and not filters and not date_range:
                st.warning("Veuillez saisir au moins un terme de recherche ou sélectionner un filtre.")
            else:
                # Show a spinner during search
                with st.spinner("Recherche en cours..."):
                    # Get fuzziness from session state or default to AUTO
                    fuzziness = st.session_state.get("fuzziness", "AUTO")
                    
                    # Use enhanced search functionality
                    results_df = enhanced_search_emails(
                        emails_df,
                        query=search_query,
                        search_mode="advanced",
                        fields=search_fields,
                        filters=filters,
                        date_range=date_range,
                        fuzziness=fuzziness,
                        size=100  # Limit to 100 results
                    )
                    
                    # Store results in session state
                    st.session_state["search_results"] = results_df
                    
                    # Display results count
                    st.subheader(f"Résultats: {len(results_df)} emails trouvés")
                    
                    # Display results using the interactive viewer
                    if not results_df.empty:
                        create_email_table_with_viewer(results_df, key_prefix="es_search_advanced")
                    else:
                        st.info("Aucun résultat trouvé. Essayez d'élargir vos critères de recherche ou de modifier le niveau de fuzziness.")
    
    with search_tabs[2]:  # Options
        st.write("Options de recherche ElasticSearch")
        
        # Fuzziness setting
        st.write("### Niveau de Fuzziness")
        fuzziness_options = [
            {"label": "AUTO (Recommandé)", "value": "AUTO"},
            {"label": "0 (Correspondance exacte)", "value": "0"},
            {"label": "1 (Permet 1 caractère de différence)", "value": "1"},
            {"label": "2 (Permet 2 caractères de différence)", "value": "2"}
        ]
        
        selected_fuzziness = st.selectbox(
            "Niveau de fuzziness:",
            options=fuzziness_options,
            format_func=lambda x: x["label"],
            index=0  # Default to AUTO
        )
        
        # Save fuzziness setting to session state
        st.session_state["fuzziness"] = selected_fuzziness["value"]
        
        # Explanation of search modes
        st.write("### Explication des modes de recherche:")
        st.markdown("""
        - **Tous les champs**: Recherche dans tous les champs (sujet, contenu, expéditeur, destinataire)
        - **Contenu et Titre**: Recherche uniquement dans le sujet et le contenu de l'email
        - **Titre uniquement**: Recherche uniquement dans le sujet de l'email
        - **Contenu uniquement**: Recherche uniquement dans le contenu de l'email
        - **Recherche avancée**: Permet de sélectionner les champs spécifiques à inclure dans la recherche
        """)
        
        # Explanation of fuzziness
        st.write("### Qu'est-ce que la fuzziness?")
        st.markdown("""
        La fuzziness permet de trouver des résultats même lorsque les termes recherchés 
        contiennent des fautes d'orthographe ou des variations.
        
        - **AUTO**: Détermine automatiquement le niveau de fuzziness en fonction de la longueur du terme
        - **0**: Correspondance exacte, sans tolérance pour les fautes
        - **1**: Permet une différence d'un caractère (insertion, suppression, substitution)
        - **2**: Permet deux différences de caractères
        """)
        
        # Reset search parameters
        if st.button("Réinitialiser les paramètres de recherche"):
            # Clear session state for search parameters
            keys_to_clear = [
                "simple_search_query", "simple_search_mode", "simple_direction",
                "advanced_search_query", "include_subject", "include_body",
                "include_from", "include_to", "advanced_start_date", "advanced_end_date",
                "advanced_sender", "advanced_recipient", "advanced_has_attachments", 
                "advanced_direction", "search_results"
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Set default fuzziness
            st.session_state["fuzziness"] = "AUTO"
            
            st.success("Paramètres réinitialisés.")
            st.rerun()
    
    # Display previous search results if available
    if "search_results" in st.session_state and not st.session_state["search_results"].empty:
        # Only show if not already displayed by a search button click
        if not (st.session_state.get("simple_search_button", False) or 
                st.session_state.get("advanced_search_button", False)):
            results_df = st.session_state["search_results"]
            st.subheader(f"Résultats précédents: {len(results_df)} emails trouvés")
            create_email_table_with_viewer(results_df, key_prefix="es_search_previous")

elif page == "Chat":
    st.subheader("Discuter avec vos archives d'emails")

    # RAG-based chat interface
    st.markdown("""
    Cette interface conversationnelle vous permet de poser des questions sur vos archives d'emails.
    Le système utilise une recherche basée sur ColBERT pour trouver les emails pertinents et fournir des informations.

    **Exemples de questions que vous pouvez poser:**
    - "Quand est prévue la prochaine réunion du comité ?"
    - "Qu'est-ce qui a été discuté dans l'email de Marie Durand ?"
    - "Qui travaille sur le projet de numérisation ?"
    - "Quels sont les délais mentionnés dans les emails récents ?"
    """)

    # First, ensure we have emails loaded
    emails_df = load_data(selected_mailbox)

    # Initialize the RAG system (if needed)
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        index_dir = initialize_rag_system(emails_df, project_root)

        # Display system status
        with st.expander("System Status", expanded=False):
            st.success(f"RAG system initialized successfully.")
            st.info(f"Using index at: {index_dir}")
            st.info(f"Email corpus size: {len(emails_df)} emails")

        # Store conversation history in session state
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Display chat history
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                st.chat_message("user").write(message["content"])
            else:
                st.chat_message("assistant").write(message["content"])
                # Display sources if available
                if "sources" in message:
                    with st.expander("Voir les sources"):
                        for source in message["sources"]:
                            st.markdown(source)

        # Chat input
        user_query = st.chat_input("Posez une question sur vos emails:")

        if user_query:
            # Display user message
            st.chat_message("user").write(user_query)

            # Add to history
            st.session_state.chat_history.append({"role": "user", "content": user_query})

            # Display thinking message
            with st.chat_message("assistant"):
                thinking_msg = st.empty()
                thinking_msg.write("Réflexion...")

                try:
                    # Get answer from RAG system
                    with st.spinner():
                        start_time = time.time()
                        answer, sources = get_rag_answer(user_query, index_dir, top_k=3)
                        elapsed_time = time.time() - start_time

                    # Replace thinking message with answer
                    thinking_msg.write(answer)

                    # Show sources in expander
                    if sources:
                        with st.expander("Voir les emails sources"):
                            for source in sources:
                                st.markdown(source)

                    # Add to history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources
                    })

                    # Show response time
                    st.caption(f"Temps de réponse: {elapsed_time:.2f} secondes")

                except Exception as e:
                    thinking_msg.error(f"Error: {str(e)}")
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"J'ai rencontré une erreur: {str(e)}"
                    })

        # Add a button to reset the chat history
        if st.session_state.chat_history and st.button("Réinitialiser la conversation"):
            st.session_state.chat_history = []
            st.rerun()

    except Exception as e:
        st.error(f"Erreur d'initialisation du système RAG: {str(e)}")
        st.info("Veuillez vous assurer que vous avez des emails chargés et essayez à nouveau.")

        # Fallback to a simple interface if RAG is not available
        user_query = st.text_input("Posez une question sur vos emails (mode basique):")
        if user_query:
            st.info("Le système RAG avancé n'est pas disponible. Utilisation du mode basique à la place.")
            st.write("Dans une implémentation complète, cela utiliserait un système RAG sophistiqué pour fournir des réponses basées sur le corpus d'emails.")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Okloa - Email Archive Analytics Platform")
