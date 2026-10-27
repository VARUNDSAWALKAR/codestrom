export function About() {
  return <section className="about-page"><div className="page-intro"><span className="eyebrow">BUILT FOR YOUR NEXT AHA MOMENT</span><h1>A clearer way to learn.</h1><p>Blu turns a question into a short visual lesson, one idea at a time.</p></div>
    <div className="about-grid">{[
      ['01', 'Watch ideas take shape', 'Follow highlighted code, diagrams, formulas, and a short recap. Each scene moves with the explanation.'],
      ['02', 'Learn in your language', 'Choose English, हिन्दी, or ಕನ್ನಡ when your local voice and translation models are ready. Captions help you follow every step.'],
      ['03', 'Keep your learning local', 'Generation runs on your local backend. Your topic and lessons stay on your machine, with no cloud AI service.'],
      ['04', 'Take the lesson with you', 'Save a rendered MP4 and subtitles to revisit a lesson at your own pace, even without opening Blu.'],
    ].map(([n, title, description]) => <article key={n}><span className="about-number">{n}</span><h2>{title}</h2><p>{description}</p></article>)}</div>
    <section className="architecture-card" aria-labelledby="architecture-title"><div className="architecture-intro"><span className="eyebrow">FROM QUESTION TO SOMETHING YOU CAN SEE</span>
      <h2 id="architecture-title">One local learning pipeline.</h2><p>Every scene comes from validated lesson data, and the same timeline drives playback and export.</p></div>
      <ol className="architecture-flow">
        {['Your topic', 'Local AI', 'Visual scenes', 'Voice + captions', 'Lesson player', 'MP4 export'].map((step, index) =>
          <li key={step}><span>{String(index + 1).padStart(2, '0')}</span><strong>{step}</strong>{index < 5 && <i aria-hidden="true">→</i>}</li>)}
      </ol><p className="architecture-note"><span aria-hidden="true">⌂</span> Your topic, generated lesson, and media stay on your machine.</p>
    </section>
    <div className="about-start"><h2>Start with something you’re curious about.</h2><p>The included sample lessons work without the AI backend. Samples use estimated timing and are silent.</p><a className="button primary" href="#/">Create a lesson →</a><a className="button secondary" href="#/sample/python">Explore a sample</a></div>
  </section>;
}
