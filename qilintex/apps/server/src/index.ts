import { startCollaboration } from './collaboration.js'
import { config } from './config.js'
import { createApp } from './app.js'

async function main() {
  const { app, store, projectFiles } = await createApp()

  app.listen(config.port, config.host, () => console.log(`REST API: http://${config.host}:${config.port}`))
  await startCollaboration(store, projectFiles)
  console.log(`Collaboration: ws://localhost:${config.collaborationPort}`)
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
