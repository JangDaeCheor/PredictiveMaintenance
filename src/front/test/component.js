export default function(component) {
  const {
    parentElement,
    setTriggerValue
  } = component;

  const button = parentElement.querySelector("#my-button");

  button.onclick = () => {
    setTriggerValue("action", "clicked");
  };
}