// 1) 대화 칸: 말풍선, 추천 카드, 예시 문장, 입력창
import { useEffect, useRef } from 'react';
import Icon from './Icon.jsx';
import RecCards from './RecCards.jsx';
import { EXAMPLES } from '../lib/util.js';

function Bubble({ m, draft, sprite, onAddPin, onAddStay, focus, onFocusPlace, profileHint }) {
  const isUser = m.role === 'user';
  const hasRec = !!(m.rec && m.rec.items && m.rec.items.length);
  const text = <div className={`tc-bubble${m.error ? ' tc-bubble--error' : ''}`}>{m.content}</div>;

  return (
    <div className={`tc-msg ${isUser ? 'tc-msg--me' : 'tc-msg--bot'}${hasRec ? ' tc-msg--rich' : ''}`}>
      {!isUser && (
        <span className="tc-avatar">
          <Icon name="mountain" sprite={sprite} />
        </span>
      )}
      {hasRec ? (
        <div className="tc-col">
          {text}
          <RecCards rec={m.rec} draft={draft} sprite={sprite} onAddPin={onAddPin} onAddStay={onAddStay}
            focus={focus} onFocus={onFocusPlace} profileHint={profileHint} />
        </div>
      ) : (
        text
      )}
    </div>
  );
}

export default function ChatPanel({
  state, sprite, input, setInput, placeholder, inputRef,
  onSend, onReset, onAddPin, onAddStay, focus, onFocusPlace, profileHint,
}) {
  const listRef = useRef(null);

  // 성별·나이대 안내는 가장 최근 추천 카드 위에만 (매번 반복하지 않기)
  let lastRec = -1;
  state.messages.forEach((m, i) => { if (m.rec && m.rec.items && m.rec.items.length) lastRec = i; });

  // 새 말풍선이 생기면 맨 아래로
  useEffect(() => {
    const box = listRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [state.messages, state.busy]);

  const onKeyDown = (e) => {
    // 한글 입력 중(조합 중)의 Enter 는 무시한다.
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) {
      e.preventDefault();
      onSend(input);
    }
  };

  return (
    <section className="tc-panel tc-chat" aria-label="AI와 대화">
      <header className="tc-panel__head">
        <h2><Icon name="chat" sprite={sprite} /> 대화</h2>
        <button type="button" className="tc-link" onClick={onReset}>새로 시작</button>
      </header>

      <div className="tc-messages" ref={listRef} aria-live="polite">
        {state.messages.map((m, i) => (
          <Bubble key={i} m={m} draft={state.draft} sprite={sprite} onAddPin={onAddPin} onAddStay={onAddStay}
            focus={focus} onFocusPlace={onFocusPlace} profileHint={i === lastRec ? profileHint : null} />
        ))}
        {state.busy && (
          <div className="tc-msg tc-msg--bot">
            <div className="tc-bubble tc-typing" aria-label="AI가 답변을 쓰는 중">
              <span /><span /><span />
            </div>
          </div>
        )}
      </div>

      <div className="tc-examples" aria-label="예시 질문" hidden={state.messages.length > 1 || state.busy}>
        {EXAMPLES.map((t) => (
          <button key={t} type="button" className="tc-example" onClick={() => onSend(t)}>{t}</button>
        ))}
      </div>

      <form className="tc-form" autoComplete="off" onSubmit={(e) => { e.preventDefault(); onSend(input); }}>
        <textarea
          ref={inputRef}
          rows={1}
          maxLength={500}
          placeholder={placeholder}
          aria-label="메시지 입력"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className="tc-send" aria-label="보내기">
          <Icon name="arrow" sprite={sprite} />
        </button>
      </form>
    </section>
  );
}
