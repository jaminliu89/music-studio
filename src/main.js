import "./app.css";
import { mount } from "svelte";
import ToneLabApp from "./App.svelte";
import DMEStudio from "./DMEStudio.svelte";

const params = new URLSearchParams(window.location.search);
const legacy = params.get("legacy") === "1";
const Surface = legacy ? ToneLabApp : DMEStudio;

const app = mount(Surface, { target: document.body });

export default app;
