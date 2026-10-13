---
name: blog-post
description: Use when publishing a finished article to one of Paul's blogs (pfischer.ca, catdevtech.net, clisten4.net). Turns a final draft into a post with title, tags, category and a generated hero image, then commits and pushes it; the VPS deploys within about five minutes.
---

# Publish a blog post

The blogs are static Next.js sites. Each lives in its own git repo under
`~/Dropbox/Development/Personal/websites/blogs/<site>`. Pushing to `main` is
publishing: the VPS checks GitHub every 5 minutes and rebuilds the site.

## Sites

| site | voice / audience | categories (subjects.json) | image style |
| --- | --- | --- | --- |
| pfischer.ca | personal essays: productivity, creativity, philosophy | read subjects.json | painterly, moody, contemplative; deep navy and blue-green palette (#03152D, #224F75, #63949E, #C8D8E7) |
| catdevtech.net | technical: Linux, containers, automation | read subjects.json | clean painterly tech illustration; cool blues; at most 5 tags |
| clisten4.net | Linux audio and music production | read subjects.json | painterly studio and sound scenes; warm moody light |

## Steps

1. **Read the final draft** you were given. It is the author's text: do not
   rewrite it. If it starts with a `# Heading`, that is the title; remove it
   from the body (the site renders the title from frontmatter).
2. **Choose the metadata**
   - `title`: the author's heading if there is one, else a short, plain title
     in the author's voice (no clickbait, no colon subtitles unless needed).
   - `slug`: 2-4 words from the title, letters/digits/underscores, e.g.
     `The_Notebook`.
   - `subject`: the id of the best-fitting existing category in the repo's
     `subjects.json`. Never invent a category.
   - `tags`: 3-6 lowercase tags (at most 5 on catdevtech.net), hyphenated.
3. **Generate the hero image** with your image generation tool:
   - 16:9, 1280x720, in the site's image style above.
   - A scene or metaphor from the post, not a literal illustration of the
     title. **No text, letters, numbers, signage or handwriting in the
     image** (generated text comes out garbled).
   - Save it as a JPEG anywhere (e.g. the run's work directory) and look at
     it. Regenerate once if it has text in it or misses the mood.
4. **Publish** with the script (it picks the post id, writes the file,
   updates `subjects.json`, copies the image, commits and pushes):

   ```bash
   python3 ~/.config/opencode/skills/blog-post/scripts/publish_post.py \
     --site pfischer.ca --body final.md --title "The Notebook" \
     --slug The_Notebook --subject 1 --tags productivity,focus,notebooks \
     --image /path/to/banner.jpg
   ```

   Add `--dry-run` first to see what it will do without writing anything.
   The script refuses to run if the repo has uncommitted changes or cannot
   fast-forward from GitHub; report that instead of working around it.
5. **Report** the post URL it prints (`https://<site>/post/<id>/`), the
   title, tags, category and image path. The site is live about 5 minutes
   after the push.

## Rules

- Never edit other posts, site code or config.
- Never force-push, rebase or commit anything except the files the script
  writes.
- If anything fails, stop and report the exact error.
