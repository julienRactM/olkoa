"""
Colbert RAG Component for Okloa.

This component provides the user interface for interacting with emails using the Colbert RAG system.
It is designed to be imported and used directly in app.py to avoid circular imports.
"""

import streamlit as st
import pandas as pd
import os
import sys
import time
from typing import List, Dict, Any, Tuple, Optional

# Import required modules from the project
from src.data.loading import load_mailboxes
from components.email_viewer import create_email_table_with_viewer

# Check if RAGAtouille is available
RAGATOUILLE_AVAILABLE = True
try:
    from src.rag.colbert_initialization import initialize_colbert_rag_system
    from src.rag.colbert_rag import colbert_rag_answer, search_with_colbert
except ImportError:
    RAGATOUILLE_AVAILABLE = False


def render_colbert_rag_component(emails_df: pd.DataFrame):
    # Check if RAGAtouille is available
    if not RAGATOUILLE_AVAILABLE:
        st.error("RAGAtouille not installed or not found in the current Python environment.")
        st.info("""
        To use ColBERT RAG, you need to install the RAGAtouille library. 
        
        Please run these commands in your terminal:
        ```
        pip install ragatouille
        pip install -r requirements.txt
        ```
        
        Make sure to install it in the same Python environment that's running your Streamlit app.
        
        If you're using a virtual environment, activate it first:
        ```
        # For venv/virtualenv
        source venv/bin/activate  # On Linux/Mac
        venv\\Scripts\\activate     # On Windows
        
        # For conda
        conda activate your_environment_name
        ```
        
        After installation, restart your Streamlit app.
        """)
        return
    """
    Render the Colbert RAG component.
    
    Args:
        emails_df: DataFrame containing email data
    """
    # Description
    st.markdown("""
    Cette interface utilise la technologie ColBERT pour rechercher dans vos emails et répondre à vos questions. 
    La technologie RAG (Retrieval-Augmented Generation) permet de retrouver les informations les plus pertinentes 
    et de les utiliser pour répondre à vos questions.

    Vous pouvez:
    1. Rechercher des emails avec une recherche sémantique puissante
    2. Poser des questions sur le contenu de vos emails
    3. Explorer les résultats avec des visualisations détaillées
    """)
    
    # Create tabs for different modes
    tabs = st.tabs(["Recherche Sémantique", "Questions-Réponses", "Configuration"])

    with tabs[0]:  # Semantic Search
        st.subheader("Recherche Sémantique avec ColBERT")
        st.write("""
        Cette recherche sémantique trouve les emails les plus pertinents en fonction du sens de votre requête,
        pas seulement des mots-clés. Essayez de poser des questions ou de décrire ce que vous cherchez.
        """)
        
        # Search input
        search_query = st.text_input(
            "Recherche:",
            placeholder="Ex: emails concernant le projet de numérisation",
            key="colbert_search_query"
        )
        
        # Search options
        col1, col2 = st.columns([1, 1])
        
        with col1:
            top_k = st.number_input(
                "Nombre de résultats:",
                min_value=1,
                max_value=20,
                value=5,
                step=1,
                key="colbert_top_k"
            )
        
        # Search button
        search_button = st.button("Rechercher", key="colbert_search_button")
        
        # Initialize and search
        if search_button and search_query:
            with st.spinner("Initialisation du système Colbert RAG..."):
                try:
                    # Get project root
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
                    
                    # Initialize Colbert RAG system
                    index_dir = initialize_colbert_rag_system(emails_df, project_root)
                    
                    # Execute search
                    with st.spinner("Recherche en cours..."):
                        start_time = time.time()
                        results = search_with_colbert(search_query, index_dir, top_k=top_k)
                        search_time = time.time() - start_time
                    
                    # Display results
                    st.subheader(f"Résultats ({len(results)} trouvés en {search_time:.2f} secondes)")
                    
                    if results:
                        # Convert results to dataframe for display
                        results_data = []
                        for result in results:
                            metadata = result.get('metadata', {})
                            # Extract the text content, limit to first 200 chars for preview
                            text_preview = result.get('text', '')[:200] + "..." if len(result.get('text', '')) > 200 else result.get('text', '')
                            
                            results_data.append({
                                "from": metadata.get("from", "Inconnu"),
                                "to": metadata.get("to", "Inconnu"),
                                "subject": metadata.get("subject", "Pas de sujet"),
                                "date": metadata.get("date", ""),
                                "body": text_preview,
                                "score": f"{result.get('score', 0):.2f}",
                                "id": metadata.get("id", ""),
                                "mailbox": metadata.get("mailbox", ""),
                            })
                        
                        # Convert to DataFrame
                        results_df = pd.DataFrame(results_data)
                        
                        # Display results
                        st.dataframe(
                            results_df[["from", "to", "subject", "date", "score", "body"]],
                            use_container_width=True,
                            hide_index=True,
                        )
                        
                        # Show detailed results in expanders
                        for i, result in enumerate(results):
                            with st.expander(f"Résultat {i+1}: {result.get('metadata', {}).get('subject', 'Pas de sujet')}"):
                                metadata = result.get('metadata', {})
                                st.write(f"**De:** {metadata.get('from', 'Inconnu')}")
                                st.write(f"**À:** {metadata.get('to', 'Inconnu')}")
                                st.write(f"**Sujet:** {metadata.get('subject', 'Pas de sujet')}")
                                st.write(f"**Date:** {metadata.get('date', 'Date inconnue')}")
                                st.write(f"**Score:** {result.get('score', 0):.4f}")
                                st.write("**Contenu:**")
                                st.text(result.get('text', 'Pas de contenu'))
                    
                    else:
                        st.info("Aucun résultat trouvé. Essayez une autre requête.")
                    
                except Exception as e:
                    st.error(f"Erreur lors de la recherche: {str(e)}")

    with tabs[1]:  # Q&A
        st.subheader("Questions et Réponses")
        st.write("""
        Posez des questions en langage naturel sur le contenu de vos emails.
        Le système recherchera les emails pertinents et formulera une réponse basée sur ces informations.
        """)
        
        # Initialize chat history if not exists
        if "colbert_chat_history" not in st.session_state:
            st.session_state.colbert_chat_history = []
        
        # Display chat history
        for message in st.session_state.colbert_chat_history:
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
            st.session_state.colbert_chat_history.append({"role": "user", "content": user_query})
            
            # Display thinking message
            with st.chat_message("assistant"):
                thinking_msg = st.empty()
                thinking_msg.write("Réflexion...")
                
                try:
                    # Get project root
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
                    
                    # Initialize Colbert RAG system
                    index_dir = initialize_colbert_rag_system(emails_df, project_root)
                    
                    # Get answer from Colbert RAG system
                    with st.spinner():
                        start_time = time.time()
                        answer, sources = colbert_rag_answer(user_query, index_dir, top_k=3)
                        elapsed_time = time.time() - start_time
                    
                    # Replace thinking message with answer
                    thinking_msg.write(answer)
                    
                    # Show sources in expander
                    if sources:
                        with st.expander("Voir les emails sources"):
                            for source in sources:
                                st.markdown(source)
                    
                    # Add to history
                    st.session_state.colbert_chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources
                    })
                    
                    # Show response time
                    st.caption(f"Temps de réponse: {elapsed_time:.2f} secondes")
                    
                except Exception as e:
                    thinking_msg.error(f"Erreur: {str(e)}")
                    st.session_state.colbert_chat_history.append({
                        "role": "assistant",
                        "content": f"J'ai rencontré une erreur: {str(e)}"
                    })
        
        # Add a button to reset the chat history
        if st.session_state.colbert_chat_history and st.button("Réinitialiser la conversation", key="reset_colbert_chat"):
            st.session_state.colbert_chat_history = []
            st.rerun()

    with tabs[2]:  # Configuration
        st.subheader("Configuration du système Colbert RAG")
        st.write("""
        Cette section vous permet de configurer et de gérer le système Colbert RAG.
        """)
        
        # Get project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        
        # Index location
        index_dir = os.path.join(project_root, 'data', 'processed', 'colbert_index')
        
        # Display index status
        index_exists = os.path.exists(os.path.join(index_dir, 'emails_index'))
        
        st.write("### État de l'index")
        if index_exists:
            st.success("L'index Colbert RAG est déjà créé et prêt à l'emploi.")
            st.write(f"Emplacement de l'index: `{index_dir}`")
            
            # Show index stats if available
            try:
                metadata_path = os.path.join(index_dir, "email_metadata.pkl")
                if os.path.exists(metadata_path):
                    import pickle
                    with open(metadata_path, "rb") as f:
                        email_metadata = pickle.load(f)
                    st.write(f"Nombre de documents indexés: {len(email_metadata)}")
                else:
                    st.write("Statistiques de l'index non disponibles.")
            except Exception as e:
                st.error(f"Erreur lors de la lecture des statistiques de l'index: {str(e)}")
        else:
            st.warning("L'index Colbert RAG n'a pas encore été créé.")
            st.write("Cliquez sur le bouton ci-dessous pour créer l'index.")
        
        # Button to rebuild index
        rebuild_button = st.button(
            "Recréer l'index",
            help="Cela recréera l'index Colbert RAG à partir de tous les emails disponibles. Cette opération peut prendre du temps.",
            key="rebuild_colbert_index"
        )
        
        if rebuild_button:
            with st.spinner("Création de l'index Colbert RAG en cours..."):
                try:
                    # Initialize Colbert RAG system with force rebuild
                    index_dir = initialize_colbert_rag_system(emails_df, project_root, force_rebuild=True)
                    st.success(f"Index créé avec succès à {index_dir}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de la création de l'index: {str(e)}")
        
        # Advanced configuration
        st.write("### Configuration avancée")
        st.info("""
        Le système Colbert RAG utilise le modèle pré-entraîné ColBERTv2.0 de Stanford NLP.
        
        Pour en savoir plus sur ColBERT, consultez:
        - [Site officiel de ColBERT](https://github.com/stanford-futuredata/ColBERT)
        - [Documentation de RAGAtouille](https://github.com/bclavie/RAGatouille)
        """)
        
        # Experimental settings
        with st.expander("Paramètres expérimentaux"):
            st.write("""
            Ces paramètres sont expérimentaux et peuvent affecter les performances du système.
            Ne les modifiez que si vous savez ce que vous faites.
            """)
            
            # Placeholder for future configuration options
            chunk_size = st.slider(
                "Taille des chunks (nombre de caractères)",
                min_value=256,
                max_value=1024,
                value=512,
                step=64,
                help="Taille des chunks utilisés pour l'indexation. Une valeur plus petite permet une recherche plus précise, mais peut réduire la cohérence contextuelle."
            )
            
            # Store in session state
            if "colbert_config" not in st.session_state:
                st.session_state.colbert_config = {}
            
            st.session_state.colbert_config["chunk_size"] = chunk_size
