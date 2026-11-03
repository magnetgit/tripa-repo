// 사이트 공용 아이콘 묶음(icons.svg)에서 하나를 꺼내 그린다. (Django 의 _icon.html 과 같은 역할)
export default function Icon({ name, sprite }) {
  return (
    <svg className="tp-icon" aria-hidden="true" focusable="false">
      <use href={`${sprite}#i-${name}`} />
    </svg>
  );
}
