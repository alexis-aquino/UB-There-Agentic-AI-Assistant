/**
 * Where the avatar goes (DFD 3.0 "Animate Avatar and Generate Speech").
 *
 * A large figure in the background of the chat: beside the conversation on wide screens,
 * faint behind it on phones. For now a placeholder silhouette. It already receives the
 * states an avatar needs to act out — listening, thinking (searching / writing), speaking —
 * so a real avatar can replace the <svg> without touching the chat. For lip sync, also pass
 * the audio level from useVoice when the avatar arrives.
 */
export default function AvatarStage({ thinking, speaking }) {
  const state = speaking ? 'speaking' : thinking ? 'thinking' : 'listening';

  return (
    <div className="avatar-stage" data-state={state} aria-hidden="true">
      <div className="avatar-glow" />
      <span className="avatar-placeholder-text">Avatar goes here</span>
      {/* Placeholder: replace with the avatar component. */}
      <svg className="avatar-placeholder" viewBox="0 0 200 240" preserveAspectRatio="xMidYMax meet">
        <circle cx="100" cy="78" r="44" />
        <path d="M18 240c6-58 40-92 82-92s76 34 82 92" />
      </svg>
    </div>
  );
}
