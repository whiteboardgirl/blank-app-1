import streamlit as st
import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import matplotlib.pyplot as plt
import networkx as nx
import plotly.express as px
import folium
from streamlit_folium import st_folium
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords

# Download NLTK data
nltk.download('stopwords')
nltk.download('wordnet')

# Initialize the lemmatizer and stopwords
lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))

# Initialize SPARQL function
def query_wikidata(sparql_query):
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setQuery(sparql_query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    
    # Parse the results into a pandas DataFrame
    data = []
    for result in results["results"]["bindings"]:
        row = {}
        for key in result:
            row[key] = result[key]['value']
        data.append(row)
    
    return pd.DataFrame(data)

# Function to preprocess text and extract a meaningful keyword
def extract_meaning(text):
    words = text.lower().split()
    meaningful_words = [lemmatizer.lemmatize(word) for word in words if word not in stop_words]
    return meaningful_words[0] if meaningful_words else words[0]

# Streamlit App
st.title("Aby Warburg-inspired Cultural Symbol Analysis Tool")

# Step 1: User inputs a SPARQL query or chooses a predefined one
st.sidebar.header("Data Querying")
sparql_query = st.text_area("Enter your SPARQL query", height=200, value="""
SELECT ?countryLabel ?capitalLabel
WHERE {
  ?country wdt:P31 wd:Q6256.
  ?country wdt:P36 ?capital.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
LIMIT 10
""")

if st.sidebar.button("Fetch Data"):
    try:
        # Fetch data from Wikidata
        df = query_wikidata(sparql_query)
        df['Meaning'] = df['countryLabel'].apply(extract_meaning)
        st.write("Query Results with Meanings:")
        st.dataframe(df)
        
        # Download the data as a CSV
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "wikidata_results.csv", "text/csv")

        # Proceed with Analysis and Visualization
        st.sidebar.header("Analysis Parameters")
        n_topics = st.sidebar.slider("Number of Topics for LDA", min_value=2, max_value=10, value=5)
        ngram_range = st.sidebar.slider("N-gram Range (1-3)", min_value=1, max_value=3, value=(1, 3))

        if st.sidebar.button("Run Analysis"):
            processed_texts = df['Meaning'].apply(lambda x: ' '.join([lemmatizer.lemmatize(word) for word in x.split() if word not in stop_words]))
            vectorizer = CountVectorizer(stop_words='english', ngram_range=(ngram_range[0], ngram_range[1]), max_features=1000)
            term_matrix = vectorizer.fit_transform(processed_texts)
            feature_names = vectorizer.get_feature_names_out()

            # LDA Topic Modeling
            lda_model = LatentDirichletAllocation(n_components=n_topics, random_state=42)
            lda_topics = lda_model.fit_transform(term_matrix)

            # Visualization of Connections
            def visualize_connections():
                G = nx.Graph()
                for idx, topic in enumerate(lda_model.components_):
                    for i in topic.argsort()[:-10 - 1:-1]:
                        G.add_edge(f'Topic {idx+1}', feature_names[i])
                plt.figure(figsize=(12, 8))
                nx.draw(G, with_labels=True, node_color='lightblue', font_size=10, node_size=3000)
                plt.title('Connections Between Topics and Symbols')
                st.pyplot(plt)

            st.subheader("Symbol Connections Visualization")
            visualize_connections()

            # Geolocation Analysis if applicable
            if 'Latitude' in df.columns and 'Longitude' in df.columns:
                st.subheader("Geolocation of Symbols")
                st.map(df[['Latitude', 'Longitude']])

                # Plotly Map
                if st.sidebar.checkbox("Show Geolocation Map"):
                    fig = px.scatter_geo(df, lat='Latitude', lon='Longitude',
                                         hover_name='countryLabel', size_max=10)
                    fig.update_layout(title='Geographic Distribution of Symbols')
                    st.plotly_chart(fig)

                # Region-specific analysis
                if 'countryLabel' in df.columns:
                    region_grouped = df.groupby('countryLabel').size().reset_index(name='Counts')
                    fig = px.choropleth(region_grouped, locations='countryLabel', locationmode='country names',
                                        color='Counts', hover_name='countryLabel', color_continuous_scale=px.colors.sequential.Plasma)
                    fig.update_layout(title='Symbol Distribution by Region')
                    st.plotly_chart(fig)

                # Heatmap Visualization
                st.subheader("Heatmap of Symbol Density")
                m = folium.Map(location=[df['Latitude'].mean(), df['Longitude'].mean()], zoom_start=2)
                heat_data = [[row['Latitude'], row['Longitude']] for index, row in df.iterrows() if not pd.isnull(row['Latitude']) and not pd.isnull(row['Longitude'])]
                folium.plugins.HeatMap(heat_data).add_to(m)
                st_folium(m, width=700)

    except Exception as e:
        st.error(f"An error occurred: {e}")
