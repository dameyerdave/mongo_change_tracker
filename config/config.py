# identifiers to replace indexes of nested arrays
replacement_identifiers = {
    'genes': 'gene',
    'genes.X.phenotypes.custom': 'phenotype',
    'genes.X.phenotypes.omim': 'phenotype',
    'evidences': 'reference'
}

state_lookup = {
  '-3': 'INITIAL',
  '-2': 'UNDEFINABLE',
  '-1': 'UNKNOWN',
  '0': 'NO_MATCH',
  '1': 'MATCH'
}

strength_lookup = {
  '-2': 'INITIAL',
  '-1': 'UNKNOWN',
  '0': 'STANDALONE',
  '1': 'SUPPORTING',
  '2': 'MODERATE',
  '3': 'STRONG',
  '4': 'VERY_STRONG',
}

# identifiers to replace indexes of nested arrays
value_replacements = {
    '.state': state_lookup,
    '.strength': strength_lookup,
    '.calculated_state': state_lookup,
    '.calculated_strength': strength_lookup
}
