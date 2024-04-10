'''
This file tries to establish all the relationships between query, candidate papers and the retrieved papers, and the 
classification of the papers. The goal is to create a matrix where the rows are candidate papers, the columns are
retrieved papers, and the values are 1 if the candidate paper cites the retrieved paper, and 0 otherwise.
Also, the classification of the papers is used to find the classification of the query and candidate papers

query_papers: The papers that are used as queries
candidate_papers: The papers that are used as candidates
retrieved_papers: The papers that are retrieved by the candidate papers

link-recorder-final-1: The data that contains the relationships between candidate papers and retrieved papers
test.qrel.cid: The data that contains the test relationships between query papers and candidate papers
classification_meta: The classification of the papers in the test set
'''
import pandas as pd
import numpy as np
import os
import json

# Load the data
candidate_retrieved_data = pd.read_csv('darwin/link-recorder-final-1', sep='\t', header=None, names=['candidate_paper', 'retrieved_paper'])
query_candidate_data = pd.read_csv('darwin/test.qrel.cid', sep=' ', header=None, names=['query', 'candidate', 'bool'])

# Load the classification meta data
with open('darwin/classification_meta.jsonl') as f:
    classification_meta = [json.loads(line) for line in f]

valid_rows = pd.DataFrame()
query_dir = 'darwin/query_papers'
candidate_dir = 'darwin/candidate_papers'
# Iterate over the rows of the data
for _, row in query_candidate_data.iterrows():
    query_file = os.path.join(query_dir, str(row['query']) + '.pdf')
    candidate_file = os.path.join(candidate_dir, str(row['candidate']) + '.pdf')

    # Check if both files exist
    if os.path.isfile(query_file) and os.path.isfile(candidate_file):
        # If both files exist, append the row to valid_rows
        valid_rows = valid_rows._append(row)

# Reset the index of valid_rows
valid_rows.reset_index(drop=True, inplace=True)
print(valid_rows.head())
print(f'Number of query candidate pairs with valid files: {len(valid_rows)}')

# unique query papers
unique_query_papers = valid_rows['query'].unique()
print(f'Number of unique query papers: {len(unique_query_papers)}')
valid_rows.to_csv('darwin/valid_query_candidate_pairs.csv', index=False)

classification_labels=[(0, 'Agricultural and Food sciences'), (1, 'Art'), (2, 'Biology'), (3, 'Business'), (4, 'Chemistry'), (5, 'Computer science'), (6, 'Economics'), (7, 'Education'), (8, 'Engineering'), (9, 'Environmental science'), (11, 'Geology'), (12, 'History'), (13, 'Law'), (14, 'Linguistics'), (15, 'Materials science'), (16, 'Mathematics'), (17, 'Medicine'), (18, 'Philosophy'), (19, 'Physics'), (20, 'Political science'), (21, 'Psychology'), (22, 'Sociology')]

# Go through each valid query paper and find the classification
found_classifications = []
print("Processing query papers and their candidate papers classification")
for query_paper in unique_query_papers:
    # print(f'Processing query paper: {query_paper} for classification task')
    # Find the classification of the query paper
    query_classification = [meta['labels'] for meta in classification_meta if meta['corpus_id'] == query_paper]
    if len(query_classification) != 0:
        print('Processing query paper: {query_paper} for classification task')
        print(f'{query_paper=}, {query_classification=}')

        # Find the candidate papers that are related to the query paper
        related_candidates = valid_rows[valid_rows['query'] == query_paper]['candidate'].tolist()
        print(f'{related_candidates=}')

        # Find the classification of each candidate paper
        for candidate_paper in related_candidates:
            classification = [meta['labels'] for meta in classification_meta if meta['corpus_id'] == candidate_paper]
            if len(classification) != 0:
                print(f'{candidate_paper=}, {classification=}')
                found_classifications.append((query_classification[0], classification[0]))

# Create a list of unique paper IDs in numerical order
candidate_paper_ids = sorted(set(candidate_retrieved_data['candidate_paper'].tolist()))
retrieved_paper_ids = sorted(set(candidate_retrieved_data['retrieved_paper'].tolist()))


# Create a dictionary that maps paper IDs to matrix indices
candidate_id_to_index = {paper_id: index for index, paper_id in enumerate(candidate_paper_ids)}
retrieved_id_to_index = {paper_id: index for index, paper_id in enumerate(retrieved_paper_ids)}

# Create an empty matrix
matrix = np.zeros((len(candidate_id_to_index), len(retrieved_id_to_index)))

# Fill in the matrix
for _, row in candidate_retrieved_data.iterrows():
    i = candidate_id_to_index[row['candidate_paper']]
    j = retrieved_id_to_index[row['retrieved_paper']]
    matrix[i, j] = 1

# Convert the matrix to a DataFrame for easier viewing
matrix_df = pd.DataFrame(matrix, index=candidate_paper_ids, columns=retrieved_paper_ids)
print(f'{matrix.shape=}')

matrix_df.to_csv('darwin/candidate_retrieved_citation_matrix.csv', index=True)
print(matrix_df.head(10))

# Are there any candidate papers don't have any retrieved papers?
papers_without_retrieved_data = []
for i in range(len(candidate_paper_ids)):
    if sum(matrix[i, :]) == 0:
        papers_without_retrieved_data.append(candidate_id_to_index[i])
print(f'Number of candidate papers without retrieved data: {len(papers_without_retrieved_data)}')

# Print the number of candidate papers that have retrieved data
print('Number of candidate papers that have retrieved data:')
papers_with_retrieved_data = set(candidate_paper_ids) - set(papers_without_retrieved_data)
print(f'\t{len(papers_with_retrieved_data)}')

print('for those candidate papers that have retrieved data:')
print(f'\tmean: {matrix_df[matrix_df.sum(axis=1) > 0].sum(axis=1).mean()}')
print(f'\tstd: {matrix_df[matrix_df.sum(axis=1) > 0].sum(axis=1).std()}')
print(f'\tmin: {matrix_df[matrix_df.sum(axis=1) > 0].sum(axis=1).min()}')
print(f'\tmax: {matrix_df[matrix_df.sum(axis=1) > 0].sum(axis=1).max()}')


found_classification_candidate = [] 
print('Processing candidate papers and their retrieved papers classification')
for candidate_paper in candidate_paper_ids:
    classification = [meta['labels'] for meta in classification_meta if meta['corpus_id'] == candidate_paper]
    if len(classification) != 0:
        print(f'{candidate_paper=}, {classification=}')
        found_classification_candidate.append(('unknown', classification[0]))

        retrieved_paper_for_candidate = matrix_df.loc[candidate_paper][matrix_df.loc[candidate_paper] == 1].index.tolist()
        print(f'{retrieved_paper_for_candidate=}')
        for retrieved_paper in retrieved_paper_for_candidate:
            classification = [meta['labels'] for meta in classification_meta if meta['corpus_id'] == retrieved_paper]
            if len(classification) != 0:
                print(f'{retrieved_paper=}, {classification=}')
                found_classification_candidate.append(('unknown', classification[0]))
