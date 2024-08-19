import streamlit as st
from groq import Groq
import dotenv
import os
import json
from PyPDF2 import PdfReader
from PIL import Image
from io import BytesIO
import pandas as pd
from fpdf import FPDF
import base64
import re

# Configuration de la page Streamlit
st.set_page_config(page_title="Créateur d'Examens Intelligents", page_icon="📝")

# Chargement des variables d'environnement
dotenv.load_dotenv()

# Structure de st.secrets pour Groq
# Vous devez ajouter ceci dans le fichier .streamlit/secrets.toml :
# [secrets]
# GROQ_API_KEY = "votre_clé_api_groq"

# Fonction pour initialiser le client Groq
def get_groq_client():
    """Initialise et renvoie un client Groq avec la clé API."""
    return Groq(api_key=st.secrets["GROQ_API_KEY"])

# Fonction pour interroger le modèle Groq
def interroger_modele_groq(messages, model_params):
    client = get_groq_client()
    response = client.chat.completions.create(
        messages=messages,
        model=model_params["model"] if "model" in model_params else "llama-3.1-70b-versatile"
    )
    return response.choices[0].message.content

# Fonction pour extraire le texte d'un PDF
def extraire_texte_du_pdf(fichier_pdf):
    lecteur_pdf = PdfReader(fichier_pdf)
    texte = ""
    for page in lecteur_pdf.pages:
        texte += page.extract_text() + "\n"
    return texte

# Fonction pour résumer un texte avec Groq
def resumer_texte(texte):
    prompt = "Veuillez résumer le texte suivant de manière concise et précise :\n\n" + texte
    messages = [
        {"role": "user", "content": prompt},
    ]
    resume = interroger_modele_groq(messages, model_params={"model": "llama-3.1-70b-versatile"})
    return resume

# Fonction pour découper un texte en morceaux plus petits
def decouper_texte(texte, max_tokens=3000):
    phrases = texte.split('. ')
    morceaux = []
    morceau = ""
    for phrase in phrases:
        if len(morceau) + len(phrase) > max_tokens:
            morceaux.append(morceau)
            morceau = phrase + ". "
        else:
            morceau += phrase + ". "
    if morceau:
        morceaux.append(morceau)
    return morceaux

# Fonction pour nettoyer et analyser les questions générées
def nettoyer_reponse_json(reponse):
    """Nettoie la réponse JSON en remplaçant les caractères d'échappement incorrects."""
    # Remplacer les échappements incorrects
    corrected_text = re.sub(r'\\(?!["\\/bfnrt])', r'\\\\', reponse)
    return corrected_text

def analyser_questions_generees(reponse):
    try:
        # Nettoyer la réponse pour corriger les échappements incorrects
        reponse = nettoyer_reponse_json(reponse)
        
        # Trouver la partie JSON dans la réponse
        debut_json = reponse.find('[')
        fin_json = reponse.rfind(']') + 1
        json_str = reponse[debut_json:fin_json]

        questions = json.loads(json_str)
        return questions
    except json.JSONDecodeError as e:
        st.error(f"Erreur de parsing JSON : {e}")
        st.error("Réponse de Groq :")
        st.text(reponse)
        return None

# Fonction pour générer des questions à choix multiples
def generer_questions_qcm(contenu_texte):
    prompt = (
        "Vous êtes un professeur dans le domaine de la Biologie des Systèmes Computationnels. "
        "En vous basant sur le document PDF fourni, créez un examen de niveau Master composé de questions à choix multiples. "
        "L'examen doit inclure 30 questions réalistes couvrant l'ensemble du contenu. Fournissez les résultats au format JSON structuré comme suit : "
        "[{'question': '...', 'choices': ['...'], 'correct_answer': '...', 'explanation': '...'}, ...]. Assurez-vous que le JSON soit valide et bien formaté."
    )
    messages = [
        {"role": "user", "content": contenu_texte},
        {"role": "user", "content": prompt},
    ]
    reponse = interroger_modele_groq(messages, model_params={"model": "mixtral-8x7b-32768"})
    return reponse

# Fonction pour obtenir une question spécifique
def obtenir_question(index, questions):
    return questions[index]

# Fonction pour initialiser l'état de session
def initialiser_etat_session(questions):
    session_state = st.session_state
    session_state.indice_question_courante = 0
    session_state.donnees_quiz = obtenir_question(session_state.indice_question_courante, questions)
    session_state.reponses_correctes = 0

# Classe pour générer un PDF
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Examen Généré', 0, 1, 'C')

    def titre_chapitre(self, titre):
        self.set_font('Arial', 'B', 12)
        self.multi_cell(0, 10, titre)
        self.ln(5)

    def corps_chapitre(self, corps):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, corps)
        self.ln()

# Fonction pour générer un PDF contenant les questions
def generer_pdf(questions):
    pdf = PDF()
    pdf.add_page()
    
    for i, q in enumerate(questions):
        question = f"Q{i+1}: {q['question']}"
        pdf.titre_chapitre(question)
        
        choix = "\n".join(q['choices'])
        pdf.corps_chapitre(choix)
        
        reponse_correcte = f"Réponse correcte : {q['correct_answer']}"
        pdf.corps_chapitre(reponse_correcte)
        
        explication = f"Explication : {q['explanation']}"
        pdf.corps_chapitre(explication)

    return pdf.output(dest="S").encode("latin1")

# Fonction principale de l'application
def main():
    if 'mode_app' not in st.session_state:
        st.session_state.mode_app = "Télécharger PDF & Générer Questions"
        
    st.sidebar.title("Créateur d'Examens Intelligents")
    
    options_mode_app = ["Télécharger PDF & Générer Questions", "Passer le Quiz", "Télécharger en PDF"]
    st.session_state.mode_app = st.sidebar.selectbox("Choisissez le mode de l'application", options_mode_app, index=options_mode_app.index(st.session_state.mode_app))
    
    st.sidebar.markdown("## À Propos")
    st.sidebar.video("https://youtu.be/zE3ToJLLSIY")
    st.sidebar.info(
        """
        **Créateur d'Examens Intelligents** est un outil innovant conçu pour aider les étudiants et les éducateurs. 
        Téléchargez vos notes de cours ou notes manuscrites pour créer des examens à choix multiples personnalisés.
        
        **Histoire :**
        Cette application a été développée dans le but de rendre la préparation aux examens plus facile et interactive pour les étudiants. 
        En tirant parti des nouveaux modèles d'IA, elle vise à transformer les méthodes d'étude traditionnelles en un processus plus engageant et 
        efficace. Que vous soyez un étudiant souhaitant tester vos connaissances ou un éducateur cherchant à créer des examens sur mesure, 
        le Créateur d'Examens Intelligents est là pour vous aider.

        **Fonctionnalités :**
        - Télécharger des documents PDF
        - Générer des questions à choix multiples
        - Passer des quiz interactifs
        - Télécharger les examens générés en PDF

        Construit avec ❤️ en utilisant le modèle Groq Mixtral.
        """
    )
    
    if st.session_state.mode_app == "Télécharger PDF & Générer Questions":
        application_telechargement_pdf()
    elif st.session_state.mode_app == "Passer le Quiz":
        if 'quiz_genere' in st.session_state and st.session_state.quiz_genere:
            if 'questions_generees' in st.session_state and st.session_state.questions_generees:
                application_quiz_qcm()
            else:
                st.warning("Aucune question générée trouvée. Veuillez d'abord télécharger un PDF et générer des questions.")
        else:
            st.warning("Veuillez d'abord télécharger un PDF et générer des questions.")
    elif st.session_state.mode_app == "Télécharger en PDF":
        application_telechargement_pdf_quiz()

# Fonction pour l'application de téléchargement et génération de PDF
def application_telechargement_pdf():

    st.title("Téléchargez votre cours - Créez votre examen")
    st.subheader("Montrez-nous les diapositives et nous faisons le reste")

    contenu_texte = ""
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    fichier_pdf_telecharge = st.file_uploader("Téléchargez un document PDF", type=["pdf"])
    if fichier_pdf_telecharge:
        texte_pdf = extraire_texte_du_pdf(fichier_pdf_telecharge)
        contenu_texte += texte_pdf
        st.success("Contenu du PDF ajouté à la session.")
    
    if len(contenu_texte) > 3000:
        contenu_texte = resumer_texte(contenu_texte)

    if contenu_texte:
        st.info("Génération de l'examen à partir du contenu téléchargé. Cela prendra une minute...")
        morceaux = decouper_texte(contenu_texte)
        questions = []
        for morceau in morceaux:
            reponse = generer_questions_qcm(morceau)
            questions_parsees = analyser_questions_generees(reponse)
            if questions_parsees:
                questions.extend(questions_parsees)
        if questions:
            st.session_state.questions_generees = questions
            st.session_state.contenu_texte = contenu_texte
            st.session_state.quiz_genere = True
            st.success("L'examen a été généré avec succès!")
        else:
            st.error("Échec de l'analyse des questions générées. Veuillez vérifier la réponse de Groq.")
    else:
        st.warning("Veuillez télécharger un PDF pour générer l'examen interactif.")

# Fonction pour soumettre une réponse
def soumettre_reponse(i, donnees_quiz):
    choix_utilisateur = st.session_state[f"choix_utilisateur_{i}"]
    st.session_state.reponses[i] = choix_utilisateur
    if choix_utilisateur == donnees_quiz['correct_answer']:
        st.session_state.feedback[i] = ("Correct", donnees_quiz.get('explanation', 'Aucune explication disponible'))
        st.session_state.reponses_correctes += 1
    else:
        st.session_state.feedback[i] = ("Incorrect", donnees_quiz.get('explanation', 'Aucune explication disponible'), donnees_quiz['correct_answer'])

# Fonction pour l'application de quiz
def application_quiz_qcm():
    st.title('Quiz à Choix Multiples')
    st.subheader('Il y a toujours une bonne réponse par question')

    questions = st.session_state.questions_generees

    if questions:  # S'assurer que la liste de questions n'est pas vide
        if 'reponses' not in st.session_state:
            st.session_state.reponses = [None] * len(questions)
            st.session_state.feedback = [None] * len(questions)
            st.session_state.reponses_correctes = 0

        for i, donnees_quiz in enumerate(questions):
            st.markdown(f"### Question {i+1} : {donnees_quiz['question']}")

            if st.session_state.reponses[i] is None:
                choix_utilisateur = st.radio("Choisissez une réponse :", donnees_quiz['choices'], key=f"choix_utilisateur_{i}")
                st.button(f"Soumettez votre réponse {i+1}", key=f"submit_{i}", on_click=soumettre_reponse, args=(i, donnees_quiz))
            else:
                st.radio("Choisissez une réponse :", donnees_quiz['choices'], key=f"choix_utilisateur_{i}", index=donnees_quiz['choices'].index(st.session_state.reponses[i]), disabled=True)
                if st.session_state.feedback[i][0] == "Correct":
                    st.success(st.session_state.feedback[i][0])
                else:
                    st.error(f"{st.session_state.feedback[i][0]} - Réponse correcte : {st.session_state.feedback[i][2]}")
                st.markdown(f"Explication : {st.session_state.feedback[i][1]}")

        if all(reponse is not None for reponse in st.session_state.reponses):
            score = st.session_state.reponses_correctes
            total_questions = len(questions)
            st.write(f"""
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh;">
                    <h1 style="font-size: 3em; color: gold;">🏆</h1>
                    <h1>Votre Score : {score}/{total_questions}</h1>
                </div>
            """, unsafe_allow_html=True)

# Fonction pour l'application de téléchargement de PDF
def application_telechargement_pdf_quiz():
    st.title('Téléchargez votre examen en PDF')

    questions = st.session_state.questions_generees

    if questions:
        for i, q in enumerate(questions):
            st.markdown(f"### Q{i+1} : {q['question']}")
            for choix in q['choices']:
                st.write(choix)
            st.write(f"**Réponse correcte :** {q['correct_answer']}")
            st.write(f"**Explication :** {q['explanation']}")
            st.write("---")  # Ligne de séparation

        pdf_bytes = generer_pdf(questions)
        st.download_button(
            label="Télécharger le PDF",
            data=pdf_bytes,
            file_name="examen_genere.pdf",
            mime="application/pdf"
        )

if __name__ == '__main__':
    main()
