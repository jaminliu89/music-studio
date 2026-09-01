import "./app.css";
import { mount } from "svelte";
import ToneLabApp from "./App.svelte";
import DMEApp from "./DMEApp.svelte";

const params = new URLSearchParams(window.location.search);
const legacy = params.get("legacy") === "1";
const Surface = legacy ? ToneLabApp : DMEApp;

const app = mount(Surface, { target: document.body });

export default app;
