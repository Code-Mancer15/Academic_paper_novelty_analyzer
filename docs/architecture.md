# Data flow

PDF/manual input → stored paper + section JSON → background analysis → local library provider → lexical TF-IDF or optional semantic embeddings → contribution matches and indicator → stored snapshot → UI/printable HTML.

A snapshot deliberately survives deletion of its input paper. Coverage and evidence strength are not scored: a small local corpus cannot establish literature coverage. There is no external metadata search or model-generated evidence.
