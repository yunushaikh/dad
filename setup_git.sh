#!/bin/bash
# Git setup helper script for DAD project

echo "DAD - Git Setup Helper"
echo "======================"
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Error: Git is not installed"
    exit 1
fi

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "Initializing git repository..."
    git init
fi

# Configure git user (if not already configured)
if [ -z "$(git config user.name)" ]; then
    echo ""
    echo "Git user configuration not found."
    read -p "Enter your git username: " git_username
    read -p "Enter your git email: " git_email
    
    git config user.name "$git_username"
    git config user.email "$git_email"
    echo "Git user configured: $git_username <$git_email>"
fi

echo ""
echo "Current git configuration:"
echo "  User: $(git config user.name)"
echo "  Email: $(git config user.email)"
echo ""

# Check for remote
if [ -z "$(git remote -v)" ]; then
    echo "No remote repository configured."
    read -p "Do you want to add a remote repository? (y/n): " add_remote
    
    if [ "$add_remote" = "y" ] || [ "$add_remote" = "Y" ]; then
        read -p "Enter remote URL (e.g., https://github.com/username/dad.git): " remote_url
        git remote add origin "$remote_url"
        echo "Remote 'origin' added: $remote_url"
    fi
else
    echo "Remote repositories:"
    git remote -v
fi

echo ""
echo "Git setup complete!"
echo ""
echo "To commit and push your code:"
echo "  1. git add ."
echo "  2. git commit -m 'Initial commit'"
echo "  3. git push -u origin master  (or main, depending on your default branch)"

