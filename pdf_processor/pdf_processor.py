#
# This is the demo of:
#   - using LayoutPDFReader to read PDF files
#   - mapping PDF elements into a property graph
#   - saving PDF elements into Neo4j
# Need to save the following variables to your own environment variables:
#   - NEO4J_URL
#   - NEO4J_USER
#   - NEO4J_PASSWORD
#   - NEO4J_DATABASE
# Arguments
#  - file_location # the folder where the PDF files are stored
#  - loglevel # log level (default: INFO)


# TODO the citation matrix is only two papers right now,
# need to be updated to the real citation matrix

import hashlib
import os
from datetime import datetime
import logging

from llmsherpa.readers import LayoutPDFReader
from neo4j import GraphDatabase

logger = logging.getLogger()
logging.basicConfig(
    datefmt = "%Y-%m-%d %H:%M:%S",
    format  = "[%(asctime)s] %(message)s",
    level   = logging.INFO
)

def ingestDocumentNeo4j(doc, doc_location, driver):
    '''
    Ingests a document into Neo4j
    :param doc: Document object
    :param doc_location: Document location
    :param driver: Neo4j driver instance
    '''

    cypher_pool = [
        # Document
        "MERGE (d:Document {url_hash: $doc_url_hash_val}) ON CREATE SET d.url = $doc_url_val RETURN d;",
        # Section
        "MERGE (p:Section {key: $doc_url_hash_val+'|'+$block_idx_val+'|'+$title_hash_val}) ON CREATE SET p.page_idx = $page_idx_val, p.title_hash = $title_hash_val, p.block_idx = $block_idx_val, p.title = $title_val, p.tag = $tag_val, p.level = $level_val RETURN p;",
        # Link Section with the Document
        "MATCH (d:Document {url_hash: $doc_url_hash_val}) MATCH (s:Section {key: $doc_url_hash_val+'|'+$block_idx_val+'|'+$title_hash_val}) MERGE (d)<-[:HAS_DOCUMENT]-(s);",
        # Link Section with a parent section
        "MATCH (s1:Section {key: $doc_url_hash_val+'|'+$parent_block_idx_val+'|'+$parent_title_hash_val}) MATCH (s2:Section {key: $doc_url_hash_val+'|'+$block_idx_val+'|'+$title_hash_val}) MERGE (s1)<-[:UNDER_SECTION]-(s2);",
        # Chunk
        "MERGE (c:Chunk {key: $doc_url_hash_val+'|'+$block_idx_val+'|'+$sentences_hash_val}) ON CREATE SET c.sentences = $sentences_val, c.sentences_hash = $sentences_hash_val, c.block_idx = $block_idx_val, c.page_idx = $page_idx_val, c.tag = $tag_val, c.level = $level_val RETURN c;",
        # Link Chunk to Section
        "MATCH (c:Chunk {key: $doc_url_hash_val+'|'+$block_idx_val+'|'+$sentences_hash_val}) MATCH (s:Section {key:$doc_url_hash_val+'|'+$parent_block_idx_val+'|'+$parent_hash_val}) MERGE (s)<-[:HAS_PARENT]-(c);"
    ]

    logger.debug(f'Ingesting Document: {doc_location}')
    logger.debug(f'doc.sections: {len(doc.sections())}')
    logger.debug(f'doc.chunks: {len(doc.chunks())}')


    with driver.session() as session:
        # Create Document node
        doc_url_val = doc_location
        doc_url_hash_val = hashlib.md5(doc_url_val.encode("utf-8")).hexdigest()
        session.run(cypher_pool[0], doc_url_hash_val=doc_url_hash_val, doc_url_val=doc_url_val)

        # Process Sections
        countSection = 0
        logger.debug(f'Processing Document: {doc_location}')
        for sec in doc.sections():
            logger.debug(f'Processing Section: {sec.title}')
            sec_title_val = sec.title
            sec_title_hash_val = hashlib.md5(sec_title_val.encode("utf-8")).hexdigest()
            sec_tag_val = sec.tag  # Assuming 'tag' differentiates sections, like 'introduction', 'methodology', etc.
            sec_level_val = sec.level  # Assuming 'level' indicates the hierarchy level of the section
            sec_page_idx_val = sec.page_idx  # Assuming 'page_idx' and 'block_idx' help uniquely identify the section
            sec_block_idx_val = sec.block_idx
            if not sec_tag_val == 'table':
                # Create Section node
                session.run(cypher_pool[1], page_idx_val=sec_page_idx_val, title_hash_val=sec_title_hash_val,
                            title_val=sec_title_val, tag_val=sec_tag_val, level_val=sec_level_val,
                            block_idx_val=sec_block_idx_val, doc_url_hash_val=doc_url_hash_val)

                # Link Section with the Document or its parent section
                sec_parent_val = str(sec.parent.to_text())
                if sec_parent_val == "None":  # use document
                    cypher = cypher_pool[2]
                    session.run(cypher, page_idx_val=sec_page_idx_val
                                    , title_hash_val=sec_title_hash_val
                                    , doc_url_hash_val=doc_url_hash_val
                                    , block_idx_val=sec_block_idx_val
                                )

                else:   # use parent section
                    sec_parent_title_hash_val = hashlib.md5(sec_parent_val.encode("utf-8")).hexdigest()
                    sec_parent_page_idx_val = sec.parent.page_idx
                    sec_parent_block_idx_val = sec.parent.block_idx

                    cypher = cypher_pool[3]
                    session.run(cypher, page_idx_val=sec_page_idx_val
                                    , title_hash_val=sec_title_hash_val
                                    , block_idx_val=sec_block_idx_val
                                    , parent_page_idx_val=sec_parent_page_idx_val
                                    , parent_title_hash_val=sec_parent_title_hash_val
                                    , parent_block_idx_val=sec_parent_block_idx_val
                                    , doc_url_hash_val=doc_url_hash_val
                                )
                countSection += 1

        # Process Chunks
        countChunk = 0
        for chk in doc.chunks():
            chunk_sentences = "\n".join(chk.sentences)  # Assuming 'sentences' is a list of sentences in the chunk
            chunk_sentences_hash_val = hashlib.md5(chunk_sentences.encode("utf-8")).hexdigest()
            chunk_block_idx_val = chk.block_idx
            chunk_page_idx_val = chk.page_idx
            chunk_tag_val = chk.tag  # Assuming 'tag' provides some categorization of chunks
            chunk_level_val = chk.level  # Assuming 'level' indicates the hierarchy level of the chunk

            if not chunk_tag_val == 'table':
                # Create Chunk node
                session.run(cypher_pool[4], sentences_hash_val=chunk_sentences_hash_val, sentences_val=chunk_sentences,
                            block_idx_val=chunk_block_idx_val, page_idx_val=chunk_page_idx_val, tag_val=chunk_tag_val,
                            level_val=chunk_level_val, doc_url_hash_val=doc_url_hash_val)

                # Link Chunk to its parent Section
                chk_parent_val = str(chk.parent.to_text())
                if chk_parent_val != 'None':
                    # parent_title_hash_val = hashlib.md5(chk.parent.title.encode("utf-8")).hexdigest()
                    chk_parent_hash_val = hashlib.md5(chk_parent_val.encode("utf-8")).hexdigest()
                    parent_block_idx_val = chk.parent.block_idx
                    session.run(cypher_pool[5], sentences_hash_val=chunk_sentences_hash_val, block_idx_val=chunk_block_idx_val,
                                parent_hash_val=chk_parent_hash_val, parent_block_idx_val=parent_block_idx_val,
                                doc_url_hash_val=doc_url_hash_val)
                    countChunk += 1

    logger.debug(f'\'{doc_location}\' Done! Summary: ')
    logger.debug(f'#Sections: {countSection}')
    logger.debug(f'#Chunks: {countChunk}')


    return doc_url_hash_val


def create_document_links(driver, citation_matrix, doc_identifiers):
    """
    Create links between document nodes based on the citation matrix.

    :param driver: Neo4j driver instance.
    :param citation_matrix: A 2D list where each element citation_matrix[i][j] is 1 if document i cites document j.
    :param doc_identifiers: List of document identifiers corresponding to the indices in the citation matrix.
    """
    with driver.session() as session:
        for i, row in enumerate(citation_matrix):
            for j, cites in enumerate(row):
                if cites:  # If document i cites document j
                    citing_doc_hash = doc_identifiers[i]
                    cited_doc_hash = doc_identifiers[j]
                    session.run(
                        "MATCH (citingDoc:Document {url_hash: $citingDocHash}), "
                        "(citedDoc:Document {url_hash: $citedDocHash}) "
                        "MERGE (citingDoc)-[:CITES]->(citedDoc)",
                        citingDocHash=citing_doc_hash,
                        citedDocHash=cited_doc_hash
                    )

if __name__ == '__main__':
    import argparse
    from pathlib import Path
    import pickle
    print(Path(__file__).parent / 'papers')
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--loglevel', help='log level (default: INFO)', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    parser.add_argument('-f', '--file_location', help='folder location of the PDF files', default=Path(__file__).parent / 'papers', type=Path)
    parser.add_argument('-c', '--citation_matrix', help='citation matrix pickle file, if None then will create random', type=argparse.FileType('rb'), default=None)
    args = parser.parse_args()
    logger.setLevel(args.loglevel)

    # The LLM Sherpa API URL
    llmsherpa_api_url = "https://readers.llmsherpa.com/api/document/developer/parseDocument?renderFormat=all"

    # Please change the following variables to your own Neo4j instance by setting the environment variables
    NEO4J_URL = os.getenv('NEO4J_URL')
    NEO4J_USER = os.getenv('NEO4J_USER')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
    NEO4J_DATABASE = os.getenv('NEO4J_DATABASE')

    def initialiseNevo4j():
        # for maintaining data integrity and preventing duplicate entries for
        # entities that should be unique, such as documents, sections, and chunks 
        cypher_schema = [
            "CREATE CONSTRAINT sectionKey IF NOT EXISTS FOR (c:Section) REQUIRE (c.key) IS UNIQUE;",
            "CREATE CONSTRAINT chunkKey IF NOT EXISTS FOR (c:Chunk) REQUIRE (c.key) IS UNIQUE;",
            "CREATE CONSTRAINT documentKey IF NOT EXISTS FOR (c:Document) REQUIRE (c.url_hash) IS UNIQUE;"
        ]
        driver = GraphDatabase.driver(NEO4J_URL, database=NEO4J_DATABASE, auth=(NEO4J_USER, NEO4J_PASSWORD))

        with driver.session() as session:
            for cypher in cypher_schema:
                session.run(cypher)
        driver.close()

    initialiseNevo4j()

    # get all documents under the folder
    pdf_files = list(args.file_location.glob('*.pdf'))

    logger.debug(f'#PDF files found: {len(pdf_files)}!')
    assert len(pdf_files) > 0, 'No PDF files found!'
    pdf_reader = LayoutPDFReader(llmsherpa_api_url)

    # parse documents and create graph
    startTime = datetime.now()
    driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD), database=NEO4J_DATABASE)
    logger.debug(f'Connecting to Neo4j at {NEO4J_URL}...')

    doc_url_hash_values = []
    for pdf_file in pdf_files:
        doc = pdf_reader.read_pdf(str(pdf_file))

        # # open a local file to write the JSON
        # with open(f'{pdf_file.name} + '.json', 'w') as f:
        #     # convert doc.json from a list to string
        #     f.write(str(doc.json))

        doc_url_hash_val = ingestDocumentNeo4j(doc, str(pdf_file), driver)
        doc_url_hash_values.append(doc_url_hash_val)

    logger.info(f'{len(pdf_files)} documents processed!')
    # Example citation matrix and document identifiers
    if args.citation_matrix is None:
        # Create Random citation Matrix
        import random
        citation_matrix = [[random.randint(0, 1) for _ in range(len(pdf_files))] for _ in range(len(pdf_files))]
    else:
        citation_matrix = pickle.load(args.citation_matrix)
    logger.debug(f'Creating document links...')
    create_document_links(driver, citation_matrix, doc_url_hash_values)
    driver.close()

    logger.info(f'Total time: {datetime.now() - startTime}')
