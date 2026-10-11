import { OpenRouter } from "@openrouter/sdk";
import "dotenv/config";

const openrouter = new OpenRouter({
    apiKey: process.env.OPENROUTER_API_KEY
});

const response = await openrouter.chat.send({
    model: "openrouter/free",
    messages: [
        {
            role: "user",
            content: "Reply exactly: OPENROUTER_OK"
        }
    ]
});

console.log(response.choices[0].message.content);
