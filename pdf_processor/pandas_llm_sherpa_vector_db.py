import pandas as pd
from pathlib import Path
import numpy as np
from llmsherpa.readers import LayoutPDFReader
import openai
from openai import OpenAI
import os
from tqdm import tqdm
from urllib3.exceptions import ProtocolError
import tiktoken

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(
    # this is also the default, it can be omitted
    api_key=os.environ['OPENAI_API_KEY'],
)


def truncate_text_tokens(text, encoding_name= 'cl100k_base', max_tokens=8191):
    """Truncate a string to have `max_tokens` according to the given encoding."""
    encoding = tiktoken.get_encoding(encoding_name)
    return encoding.encode(text)[:max_tokens]


def get_embedding(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    text = truncate_text_tokens(text)
    return client.embeddings.create(input=[text], model=model).data[0].embedding


def create_df(pdf_urls):
    llmsherpa_api_url = "https://readers.llmsherpa.com/api/document/developer/parseDocument?renderFormat=all"
    # llmsherpa_api_url = "http://172.17.0.3:5001/api/parseDocument?renderFormat=all"
    pdf_reader = LayoutPDFReader(llmsherpa_api_url)

    # Initialize a list to hold the data
    data = []
    failed = []
    for pdf_url in tqdm(pdf_urls):
        print(f'Processing {pdf_url}')
        try:
            doc = pdf_reader.read_pdf(str(pdf_url))
        except KeyError as e:
            print(f'Skipping {pdf_url} due to KeyError: {e}')
            failed.append(pdf_url)
            continue
        except ProtocolError as e:
            print(f'Skipping {pdf_url} due to ProtocolError: {e}')
            failed.append(pdf_url)
            continue
        except Exception as e:
            print(f'Failed to process {pdf_url} due to {e}')
            failed.append(pdf_url)
            continue

        # Append to data for each chunk in the document
        for i, chunk in enumerate(doc.chunks()):
            text = chunk.to_context_text()
            section = str(chunk.parent.to_text())
            data.append({"file_id": pdf_url.stem, "text": text, "vector_embedding": get_embedding(text), "section": section, "document_id": i})

    # Convert the list to a DataFrame
    print(f'Failed to process {len(failed)} pdfs')
    with open('failed_pdfs', 'w') as f:
        for pdf in failed:
            f.write(f'{pdf}\n')
    return pd.DataFrame(data)



if __name__ == "__main__":

    redo_embedding = True
    with open('darwin/qpaper_to_emb', 'r') as f:
        query_papers = [line.strip() for line in f]

    with open('darwin/cpaper_to_emb', 'r') as f:
        candidate_papers = [line.strip() for line in f]

    print(f'len(query_papers): {len(query_papers)}')
    print(f'len(candidate_papers): {len(candidate_papers)}')

    qpdf_urls = [Path(f'darwin/query_papers/{pdf}.pdf') for pdf in query_papers]
    cdpdf_urls = [Path(f'darwin/candidate_papers/{pdf}.pdf') for pdf in candidate_papers]

    # If the query_vector_db.csv exists, read it
    if os.path.exists('query_vector_db.csv') and not redo_embedding:
        print('Reading query_vector_db.csv')
        query_df = pd.read_csv('query_vector_db.csv')
    else:
        query_df = create_df(qpdf_urls)
        query_df.to_csv('query_vector_db.csv', index=False)

    if os.path.exists('candidate_vector_db.csv') and not redo_embedding:
        print('Reading candidate_vector_db.csv')
        candidade_df= pd.read_csv('candidate_vector_db.csv')
    else:
        candidate_df = create_df(cdpdf_urls)
        candidate_df.to_csv('candidate_vector_db.csv', index=False)
