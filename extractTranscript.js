const fs = require("fs")
const xml2js = require("xml2js")
const path = require("path")
const os = require("os")

function formatTimestamp(seconds) {
	const h = Math.floor(seconds / 3600)
	const m = Math.floor((seconds % 3600) / 60)
	const s = Math.floor(seconds % 60)

	return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
}

function extractTranscript(ttmlContent, outputPath, includeTimestamps = false) {
	const parser = new xml2js.Parser()

	parser.parseString(ttmlContent, (err, result) => {
		if (err) {
			throw err
		}

		let transcript = []

		function extractTextFromSpans(spans) {
			let text = ""
			spans.forEach((span) => {
				if (span.span) {
					text += extractTextFromSpans(span.span)
				} else if (span._) {
					text += span._ + " "
				}
			})
			return text
		}

		const paragraphs = result.tt.body[0].div[0].p

		paragraphs.forEach((paragraph) => {
			if (paragraph.span) {
				const paragraphText = extractTextFromSpans(paragraph.span).trim()
				if (paragraphText) {
					if (includeTimestamps && paragraph.$ && paragraph.$.begin) {
						const timestamp = formatTimestamp(parseFloat(paragraph.$.begin))
						transcript.push(`[${timestamp}] ${paragraphText}`)
					} else {
						transcript.push(paragraphText)
					}
				}
			}
		})

		const outputText = transcript.join("\n\n")
		fs.writeFileSync(outputPath, outputText)
		console.log(`Transcript saved to ${outputPath}`)
	})
}

function findTTMLFiles(dir) {
	const files = fs.readdirSync(dir)
	let ttmlFiles = []

	files.forEach((file) => {
		const fullPath = path.join(dir, file)
		const stat = fs.statSync(fullPath)

		if (stat.isDirectory()) {
			ttmlFiles = ttmlFiles.concat(findTTMLFiles(fullPath))
		} else if (path.extname(fullPath) === ".ttml") {
			const match = fullPath.match(/PodcastContent([^\/]+)/)
			if (match) {
				ttmlFiles.push({
					path: fullPath,
					id: match[1],
				})
			}
		}
	})

	return ttmlFiles
}

// Create output directory if it doesn't exist
if (!fs.existsSync("./transcripts")) {
	fs.mkdirSync("./transcripts")
}

const includeTimestamps = process.argv.includes("--timestamps")

if (process.argv.length >= 4 && !includeTimestamps) {
	// Individual file mode
	const inputPath = process.argv[2]
	const outputPath = process.argv[3]
	fs.readFile(inputPath, "utf8", (err, data) => {
		if (err) {
			console.error(err)
			return
		}
		extractTranscript(data, outputPath, includeTimestamps)
	})
} else if (process.argv.length === 2 || (process.argv.length === 3 && includeTimestamps)) {
	// Batch mode - process all TTML files
	const ttmlBaseDir = path.join(os.homedir(), "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML")

	console.log("Searching for TTML files...")
	const ttmlFiles = findTTMLFiles(ttmlBaseDir)

	console.log(`Found ${ttmlFiles.length} TTML files`)

	// Create a map to track filename occurrences
	const filenameCounts = new Map()

	ttmlFiles.forEach((file) => {
		const baseFilename = file.id
		const count = filenameCounts.get(baseFilename) || 0
		const suffix = count === 0 ? "" : `-${count}`
		const outputPath = path.join("./transcripts", `${baseFilename}${suffix}.txt`)

		// Increment the count for this filename
		filenameCounts.set(baseFilename, count + 1)

		const data = fs.readFileSync(file.path, "utf8")
		extractTranscript(data, outputPath, includeTimestamps)
	})
} else {
	console.error("Invalid arguments.")
	console.error("Usage:")
	console.error("  For single file: node extractTranscript.js <input.ttml> <output.txt> [--timestamps]")
	console.error("  For all files: node extractTranscript.js [--timestamps]")
	process.exit(1)
}
