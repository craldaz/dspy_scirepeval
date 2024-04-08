#!/usr/bin/env python3
import dotenv
dotenv.load_dotenv()

import argparse
import os
import time
from requests import Session
from typing import Generator, Union

import urllib3
urllib3.disable_warnings()

S2_API_KEY = os.environ['S2_API_KEY']


def get_paper(session: Session, c_id: str, fields: str = 'paperId,title', **kwargs) -> dict:
    params = {
        'fields': fields,
        **kwargs,
    }
    headers = {
        'X-API-KEY': S2_API_KEY,
    }

    with session.get(f'https://api.semanticscholar.org/graph/v1/paper/CorpusID:{c_id}', params=params, headers=headers) as response:
        response.raise_for_status()
        return response.json()


def download_pdf(session: Session, url: str, path: str, user_agent: str = 'requests/2.0.0'):
    # send a user-agent to avoid server error
    headers = {
        'user-agent': user_agent,
    }

    # stream the response to avoid downloading the entire file into memory
    with session.get(url, headers=headers, stream=True, verify=False) as response:
        # check if the request was successful
        response.raise_for_status()

        if response.headers['content-type'] != 'application/pdf':
            raise Exception('The response is not a pdf')

        with open(path, 'wb') as f:
            # write the response to the file, chunk_size bytes at a time
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)


def download_paper(session: Session, c_id: str, directory: str = 'retrieved_papers', user_agent: str = 'requests/2.0.0') -> Union[str, None]:
    paper = get_paper(session, c_id, fields='corpusId,paperId,isOpenAccess,openAccessPdf')

    # check if the paper is open access
    if not paper['isOpenAccess']:
        return None

    if paper['openAccessPdf'] is None:
        return None
    corpusId: str = paper['corpusId']
    paperId: str = paper['paperId']
    pdf_url: str = paper['openAccessPdf']['url']
    pdf_path = os.path.join(directory, f'{corpusId}.pdf')

    # create the directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)

    # check if the pdf has already been downloaded
    if not os.path.exists(pdf_path):
        download_pdf(session, pdf_url, pdf_path, user_agent=user_agent)

    return pdf_path, corpusId


def download_papers(retrieved_dict, directory: str = 'retrieved_papers', user_agent: str = 'requests/2.0.0') -> Generator[tuple[str, Union[str, None, Exception]], None, None]:
    # use a session to reuse the same TCP connection
    link_dict = {}
    with Session() as session:
        for test_set_paper, retrieved_paper in retrieved_dict.items():
            for c_id in retrieved_paper:
                try:
                    pdf_path, corpusId = download_paper(session, c_id, directory=directory, user_agent=user_agent)
                    if pdf_path:
                        link_dict[test_set_paper] = corpusId
                        print(f"Downloaded '{corpusId}' to '{pdf_path}'")
                        break
                except Exception as e:
                    continue
    return link_dict
  

def main(args: argparse.Namespace) -> None:
    start = time.time()
    retrieved_dict = {}
    with open (args.input_file, 'r') as input_file:
        for line in input_file:
            temp = line.split('\t')
            score = temp[0]
            if score != '1.000000':
                test_set_paper = temp[1].strip()
                retrieved_paper = temp[2].strip()
                if test_set_paper not in retrieved_dict:
                    retrieved_dict[test_set_paper] = []
                retrieved_dict[test_set_paper].append(retrieved_paper)

    print("Loaded retrieved_dict.", time.time() - start)
    link_dict = download_papers(retrieved_dict, directory=args.directory, user_agent=args.user_agent)
    print("Downloaded the papers.", time.time() - start)
    with open(args.link_recorder, 'a') as f:
        for k, v in link_dict.items():
            f.write(f'{k}\t{v}\n')
    print("Created the link tracker.", time.time() - start)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', '-d', default='retrieved_papers')
    parser.add_argument('--user-agent', '-u', default='requests/2.0.0')
    parser.add_argument('--input-file', '-i', type=str, default='')
    parser.add_argument('--link-recorder', '-l', type=str, default='')
    # parser.add_argument('paper_ids', nargs='+', default=[])
    args = parser.parse_args()
    main(args)
