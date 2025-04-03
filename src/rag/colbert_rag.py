"""
Colbert RAG implementation for the Okloa project.

This module provides functionality for creating a RAG system using the 
RAGAtouille library with ColBERTv2.0 retriever for email data.
"""

import os
import sys
import pandas as pd
import mailbox
import email
from typing import List, Dict, Any, Tuple, Optional
import pickle
import json
from pathlib import Path
from datetime import datetime
import tempfile
import shutil
import textwrap

# Import RAGAtouille library
RAGATOUILLE_AVAILABLE = True
try:
    from ragatouille import RAGPretrainedModel
except ImportError:
    print("RAGAtouille not installed. Please install it with 'pip install ragatouille'")
    RAGATOUILLE_AVAILABLE = False

# Parse email functionality from the loading module
from src.data.loading import parse_email_message, load_mbox_file


def prepare_email_for_rag(email_data: Dict[str, Any]) -> str:
    """
    Format an email for indexing in the RAG system.
    
    Args:
        email_data: Dictionary containing parsed email data
        
    Returns:
        Formatted string representation of the email
    """
    formatted_email = f"From: {email_data.get('from', '')}\n"
    formatted_email += f"To: {email_data.get('to', '')}\n"
    
    if email_data.get('cc'):
        formatted_email += f"Cc: {email_data.get('cc', '')}\n"
        
    formatted_email += f"Subject: {email_data.get('subject', '')}\n"
    formatted_email += f"Date: {email_data.get('date', '')}\n"
    
    # Add body
    if email_data.get('body'):
        formatted_email += f"\n{email_data.get('body', '')}"
    
    return formatted_email


def load_and_prepare_emails(mailbox_paths: List[str]) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Load emails from multiple mailbox files and prepare them for RAG.
    
    Args:
        mailbox_paths: List of paths to mailbox files
        
    Returns:
        List of tuples with (formatted_email, metadata)
    """
    all_emails = []
    
    for mbox_path in mailbox_paths:
        try:
            # Process each mbox file
            mbox = mailbox.mbox(mbox_path)
            
            for i, message in enumerate(mbox):
                try:
                    # Parse the email message
                    email_data = parse_email_message(message)
                    
                    # Generate a unique ID
                    email_id = email_data.get("message_id", f"email_{Path(mbox_path).stem}_{i}")
                    
                    # Format the email for RAG
                    formatted_email = prepare_email_for_rag(email_data)
                    
                    # Create metadata for retrieval
                    metadata = {
                        "id": email_id,
                        "from": email_data.get("from", ""),
                        "to": email_data.get("to", ""),
                        "subject": email_data.get("subject", ""),
                        "date": str(email_data.get("date", "")),
                        "mailbox": Path(mbox_path).parent.name,
                        "direction": email_data.get("direction", ""),
                        "has_attachments": email_data.get("has_attachments", False),
                    }
                    
                    # Add to the collection
                    all_emails.append((formatted_email, metadata))
                    
                except Exception as e:
                    print(f"Error processing email: {e}")
            
        except Exception as e:
            print(f"Error loading mailbox {mbox_path}: {e}")
    
    return all_emails


def initialize_colbert_rag(emails_data: List[Tuple[str, Dict[str, Any]]], index_path: str) -> str:
    """
    Initialize the Colbert RAG system with email data.
    
    Args:
        emails_data: List of tuples with (formatted_email, metadata)
        index_path: Path to save the index
        
    Returns:
        Path to the index directory
    """
    # Ensure the index directory exists
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    
    # Separate emails and metadata
    email_texts = [email[0] for email in emails_data]
    email_ids = [f"email_{i}" for i in range(len(emails_data))]
    email_metadata = [email[1] for email in emails_data]
    
    try:
        # Initialize the RAG model with ColBERTv2.0
        rag_model = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")
        
        # Index the email collection
        print(f"Indexing {len(email_texts)} emails...")
        rag_model.index(
            collection=email_texts,
            document_ids=email_ids,
            document_metadatas=email_metadata,
            index_name="emails_index",
            max_document_length=512,  # Adjust based on email size
            split_documents=True      # Split long emails into chunks
        )
        
        # Save the model to the specified path
        rag_model.save(index_path)
        
        # Save the email metadata mapping for later use
        metadata_path = os.path.join(index_path, "email_metadata.pkl")
        with open(metadata_path, "wb") as f:
            pickle.dump(email_metadata, f)
        
        return index_path
        
    except Exception as e:
        print(f"Error initializing Colbert RAG: {e}")
        raise


def load_colbert_rag(index_path: str):
    """
    Load a previously initialized Colbert RAG model.
    
    Args:
        index_path: Path to the saved index directory
        
    Returns:
        Loaded RAG model
    """
    try:
        # Load the RAG model from the specified path
        rag_model = RAGPretrainedModel.from_index(index_path)
        return rag_model
    except Exception as e:
        print(f"Error loading Colbert RAG model: {e}")
        raise


def search_with_colbert(query: str, index_path: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Search emails using the Colbert RAG model.
    
    Args:
        query: Query string
        index_path: Path to the index directory
        top_k: Number of results to return
        
    Returns:
        List of search results with metadata
    """
    try:
        # Load the RAG model
        rag_model = load_colbert_rag(index_path)
        
        # Search for the query
        results = rag_model.search(query=query, k=top_k)
        
        # Load the email metadata
        metadata_path = os.path.join(index_path, "email_metadata.pkl")
        with open(metadata_path, "rb") as f:
            email_metadata = pickle.load(f)
        
        # Enrich results with metadata
        enriched_results = []
        for result in results:
            # Extract index from text_id (format: "email_X_chunk_Y")
            try:
                # Handle different ID formats
                if "_chunk_" in result["text_id"]:
                    email_id = result["text_id"].split("_chunk_")[0]
                    email_index = int(email_id.replace("email_", ""))
                else:
                    email_index = int(result["text_id"].replace("email_", ""))
                
                # Get metadata if available
                metadata = email_metadata[email_index] if email_index < len(email_metadata) else {}
                
                # Create enriched result
                enriched_result = {
                    "text": result["text"],
                    "text_id": result["text_id"],
                    "score": result["score"],
                    "metadata": metadata
                }
                
                enriched_results.append(enriched_result)
                
            except (ValueError, IndexError) as e:
                print(f"Error enriching result: {e}")
                # Still include the result without enrichment
                enriched_results.append(result)
        
        return enriched_results
        
    except Exception as e:
        print(f"Error searching with Colbert: {e}")
        raise


def get_all_mbox_paths(data_dir: str) -> List[str]:
    """
    Get paths to all mbox files in the data directory.
    
    Args:
        data_dir: Path to the data directory
        
    Returns:
        List of paths to mbox files
    """
    mbox_paths = []
    
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('.mbox'):
                mbox_paths.append(os.path.join(root, file))
    
    return mbox_paths


def format_result_preview(result: Dict[str, Any]) -> str:
    """
    Format a search result for preview display.
    
    Args:
        result: Search result dictionary with metadata
        
    Returns:
        Formatted preview string
    """
    metadata = result.get('metadata', {})
    preview = f"**De:** {metadata.get('from', 'Inconnu')}\n"
    preview += f"**À:** {metadata.get('to', 'Inconnu')}\n"
    preview += f"**Sujet:** {metadata.get('subject', 'Pas de sujet')}\n"
    preview += f"**Date:** {metadata.get('date', 'Date inconnue')}\n"
    
    # Include the text content
    if result.get('text'):
        # Wrap to multiple lines for better readability
        wrapped_text = textwrap.fill(result['text'], width=80)
        preview += f"**Contenu:**\n```\n{wrapped_text}\n```\n"
    
    # Add relevance score if available
    if 'score' in result:
        preview += f"**Score de pertinence:** {result['score']:.2f}\n"
    
    return preview


def generate_answer(query: str, results: List[Dict[str, Any]]) -> str:
    """
    Generate an answer based on the search results.
    
    Args:
        query: User query
        results: Search results from Colbert
        
    Returns:
        Generated answer
    """
    if not results:
        return "Je n'ai pas trouvé d'informations pertinentes dans les archives d'emails pour répondre à votre question."
    
    # Simple approach to generate a response based on the retrieved information
    answer = f"D'après les emails récupérés, voici ce que j'ai trouvé concernant votre question:\n\n"
    
    for i, result in enumerate(results[:3]):  # Use top 3 results
        metadata = result.get('metadata', {})
        sender = metadata.get('from', 'Expéditeur inconnu')
        subject = metadata.get('subject', 'Pas de sujet')
        date = metadata.get('date', 'Date inconnue')
        
        answer += f"**Email {i+1}:** De {sender}, sujet \"{subject}\" (le {date})\n"
        
        # Include a snippet of the content
        if result.get('text'):
            text = result.get('text')
            # Get a relevant excerpt (around 200 characters)
            if len(text) > 200:
                excerpt = text[:200] + "..."
            else:
                excerpt = text
            answer += f"Contenu: \"{excerpt}\"\n\n"
    
    return answer


def colbert_rag_answer(query: str, index_path: str, top_k: int = 5) -> Tuple[str, List[str]]:
    """
    Get an answer to a query using Colbert RAG.
    
    Args:
        query: User query
        index_path: Path to the index directory
        top_k: Number of results to consider
        
    Returns:
        Tuple of (answer, formatted source previews)
    """
    # Search with Colbert
    results = search_with_colbert(query, index_path, top_k=top_k)
    
    # Generate answer
    answer = generate_answer(query, results)
    
    # Format sources for display
    source_previews = [format_result_preview(result) for result in results]
    
    return answer, source_previews
