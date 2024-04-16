import pandas as pd
from pathlib import Path
import os
import openai
from openai import OpenAI
from PyPDF2 import PdfReader
import tiktoken
import tiktoken
from PyPDF2 import PdfReader
import concurrent.futures

# Set up the OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(
    # this is also the default, it can be omitted
    api_key=os.environ['OPENAI_API_KEY'],
)

def chunk_text_to_fit_tokens(text, encoding_name='cl100k_base', max_tokens=8191):
    """Chunk text to ensure each chunk fits within a specified number of tokens."""
    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(text)

    # Chunk tokens to fit within the max_tokens limit
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_token_ids = tokens[i:i + max_tokens]
        chunk_text = encoding.decode(chunk_token_ids)
        chunks.append(chunk_text)
    return chunks

def chunk_pdf_with_tiktoken(file_path, encoding_name='cl100k_base', max_tokens=8191):
    """Read PDF file and chunk its text into sections, each fitting within the token limit."""
    try:
        pdf = PdfReader(file_path)
        full_text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + " "  # Adding space to separate text between pages
        full_text = full_text.replace("\n", " ")
        return chunk_text_to_fit_tokens(full_text, encoding_name, max_tokens)
    except Exception as e:
        print(f"Failed to process {file_path} with error: {e}")
        return []

def sanitize_text(text):
    """Sanitize text for safe CSV/TSV output."""
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = text.replace('"', "'")  # Replace double quotes with single quotes to avoid issues with CSV
    return text

def embedding_to_string(embedding):
    """Convert embedding list to a string."""
    return ','.join(map(str, embedding))


def create_df_debug(file_paths, encoding_name='cl100k_base', max_tokens=1000):
    """Create a DataFrame with file ID, text chunks, and their embeddings."""
    data = []
    for file_path in file_paths:
        file_id = file_path.stem
        chunks = chunk_pdf_with_tiktoken(file_path, encoding_name, max_tokens)
        for i, chunk in tqdm(enumerate(chunks)):
            sanitized_chunk = sanitize_text(chunk)
            embedding = get_embedding(chunk)  # Get embeddings normally
            embedding_str = embedding_to_string(embedding)  # Convert embedding to a string
            data.append({
                "file_id": file_id,
                "chunk_id": i,
                "text": sanitized_chunk,
                "vector_embedding": embedding_str
            })
    return pd.DataFrame(data)


def get_embeddings(texts, model="text-embedding-3-small"):
    try:
        response = client.embeddings.create(input=texts, model=model)
        # Extracting embeddings directly from the response object
        embeddings = [embedding.embedding for embedding in response.data]
        return embeddings
    except Exception as e:
        print("Error during API call:", e)
        return []


def create_df(file_paths, encoding_name='cl100k_base', max_tokens=1000, batch_size=10):
    """Create a DataFrame with file ID, text chunks, and their embeddings in batches."""
    data = []
    batch_texts = []
    batch_identifiers = []  # To track file_id and chunk_id for reassembly

    for file_path in file_paths:
        file_id = file_path.stem
        chunks = chunk_pdf_with_tiktoken(file_path, encoding_name, max_tokens)
        for i, chunk in enumerate(chunks):
            sanitized_chunk = sanitize_text(chunk)
            batch_texts.append(sanitized_chunk)
            batch_identifiers.append((file_id, i))

            # Process in batches
            if len(batch_texts) == batch_size:
                embeddings = get_embeddings(batch_texts)
                for idx, embedding in enumerate(embeddings):
                    file_id, chunk_id = batch_identifiers[idx]
                    embedding_str = embedding_to_string(embedding)
                    data.append({
                        "file_id": file_id,
                        "chunk_id": chunk_id,
                        "text": batch_texts[idx],
                        "vector_embedding": embedding_str
                    })
                # Clear batch lists
                batch_texts = []
                batch_identifiers = []

    # Process any remaining items in the batch
    if batch_texts:
        embeddings = get_embeddings(batch_texts)
        for idx, embedding in enumerate(embeddings):
            file_id, chunk_id = batch_identifiers[idx]
            embedding_str = embedding_to_string(embedding)
            data.append({
                "file_id": file_id,
                "chunk_id": chunk_id,
                "text": batch_texts[idx],
                "vector_embedding": embedding_str
            })

    return pd.DataFrame(data)



if __name__ == "__main__":
    redo_embedding = True
    with open('darwin/qpaper_to_emb', 'r') as f:
        query_papers = [line.strip() for line in f]

    with open('darwin/cpaper_to_emb', 'r') as f:
        candidate_papers = [line.strip() for line in f]

    print(f'len(query_papers): {len(query_papers)}')
    print(f'len(candidate_papers): {len(candidate_papers)}')
    query_papers = [Path(f'darwin/query_papers/{pdf}.pdf') for pdf in query_papers]
    candidate_papers = [Path(f'darwin/candidate_papers/{pdf}.pdf') for pdf in candidate_papers]

    # # Example usage
    # print(truncate_text_tokens("Example text that might be too long and needs to be truncated.", 'cl100k_base', 10))

    if os.path.exists('query_vector_db.csv') and not redo_embedding:
        query_df = pd.read_csv('query_vector_db.csv')
        print("Dataframe loaded from query_vector_db.csv.")
    else:
        query_df = create_df(query_papers)
        query_df.to_csv('query_vector_db.csv', index=False)
        print("Dataframe created and saved.")
        print(query_df.head())
    print('done with query_df')
    if os.path.exists('candidate_vector_db.csv') and not redo_embedding:
        print('Reading candidate_vector_db.csv')
        candidade_df= pd.read_csv('candidate_vector_db.csv')
    else:
        candidate_df = create_df(candidate_papers)
        candidate_df.to_csv('candidate_vector_db.csv', index=False)
