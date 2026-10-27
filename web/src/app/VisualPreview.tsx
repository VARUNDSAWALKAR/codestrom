export function VisualPreview() {
  return <aside className="preview-column" aria-label="Example visual lesson">
    <div className="preview-caption"><span className="eyebrow">A LITTLE LESS ABSTRACT.</span><span className="preview-live"><i /> A lot more “aha!”</span></div>
    <a href="#/sample/python" className="visual-preview" aria-label="Play Python loop sample">
      <div className="preview-topline"><span className="preview-subject">&lt;/&gt; PROGRAMMING</span><span>SCENE 02 / 04</span></div>
      <h2>Python for loops<span>One loop. Three little steps.</span></h2>
      <div className="preview-editor"><div className="editor-title"><span><i /><i /><i /></span><span>hello_loop.py</span><span>Python</span></div>
        <div className="preview-code"><div><span className="line-no">1</span><code><b>for</b> i <b>in</b> <em>range</em>(<strong>3</strong>):</code></div><div className="code-active"><span className="line-no">2</span><code>    <em>print</em>(i)</code><span className="executing">← now</span></div></div>
      </div>
      <div className="preview-state"><div><span>CURRENT STATE</span><p><code>i</code><span>→</span><strong>1</strong></p></div><div><span>OUTPUT</span><p className="preview-output">0 <strong>1<span className="cursor" /></strong></p></div></div>
      <div className="preview-subtitles">“Now the variable i contains the value one.”</div>
      <div className="preview-bottom"><span className="preview-play">▶</span><span>See it. Understand it.</span><span>Try this lesson <b>↗</b></span></div>
    </a>
    <div className="preview-note"><span className="note-icon">✧</span><p>More than an explanation.<br /><strong>A concept you can actually see.</strong></p><span className="note-curve" aria-hidden="true">↗</span></div>
    <div className="scene-formats"><span>Code walkthroughs</span><span>Diagrams</span><span>Formulas</span></div>
  </aside>;
}
