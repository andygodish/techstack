---
tags: [quick-reference, commands, troubleshooting, kubernetes, tmux, docker, linux, devops, cli, productivity]
---

# Quick Commands

A collection of essential command-line utilities and quick reference commands for common development and operations tasks.

## tmux Session Management

### List active sessions
```bash
tmux list-sessions
```

### Kill a specific session
```bash
tmux kill-session -t [SESSION-NAME]
```

### Create new session with name
```bash
tmux new-session -d -s [SESSION-NAME]
```

### Attach to existing session
```bash
tmux attach-session -t [SESSION-NAME]
```

### Rename current session
```bash
tmux rename-session [NEW-NAME]
```

## Kubernetes Quick Commands

### Get pods in specific namespace
```bash
kubectl get pods -n [NAMESPACE]
```

### Check pod logs
```bash
kubectl logs [POD-NAME] -n [NAMESPACE] --follow
```

### Port forward to local machine
```bash
kubectl port-forward [POD-NAME] [LOCAL-PORT]:[POD-PORT] -n [NAMESPACE]
```

### Get service accounts with roles
```bash
kubectl get serviceaccounts -n [NAMESPACE]
kubectl describe serviceaccount [SERVICE-ACCOUNT] -n [NAMESPACE]
```

### Quick pod troubleshooting
```bash
# Get pod details
kubectl describe pod [POD-NAME] -n [NAMESPACE]

# Execute into pod
kubectl exec -it [POD-NAME] -n [NAMESPACE] -- /bin/bash

# Check resource usage
kubectl top pods -n [NAMESPACE]
```

## Docker Commands

### Clean up unused resources
```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Clean everything
docker system prune -a --volumes
```

### Container inspection
```bash
# List running containers
docker ps

# View container logs
docker logs [CONTAINER-NAME] --follow

# Execute into running container
docker exec -it [CONTAINER-NAME] /bin/bash
```

## AWS CLI Quick Commands

### S3 Operations
```bash
# List buckets
aws s3 ls

# Sync directory to S3
aws s3 sync ./local-folder s3://[S3-BUCKET-NAME]/path/

# Copy single file
aws s3 cp file.txt s3://[S3-BUCKET-NAME]/path/
```

### IAM Role Information
```bash
# List roles
aws iam list-roles --query 'Roles[*].RoleName'

# Get role details
aws iam get-role --role-name [ROLE-NAME]

# List attached policies
aws iam list-attached-role-policies --role-name [ROLE-NAME]
```

## Network Diagnostics

### Connection testing
```bash
# Test connectivity
ping [DOMAIN-NAME]
telnet [DOMAIN-NAME] 80

# Check listening ports
netstat -tlnp
ss -tlnp

# DNS resolution
nslookup [DOMAIN-NAME]
dig [DOMAIN-NAME]
```

### Service health checks
```bash
# Check service status
systemctl status [SERVICE-NAME]

# View service logs
journalctl -u [SERVICE-NAME] --follow

# Restart service
sudo systemctl restart [SERVICE-NAME]
```

## Git Quick Commands

### Branch management
```bash
# List branches
git branch -a

# Create and switch to new branch
git checkout -b [BRANCH-NAME]

# Delete local branch
git branch -d [BRANCH-NAME]

# Delete remote branch
git push origin --delete [BRANCH-NAME]
```

### Quick fixes
```bash
# Undo last commit (keep changes)
git reset --soft HEAD~1

# Stash current changes
git stash push -m "[STASH-MESSAGE]"

# Apply and drop stash
git stash pop

# View commit history (one line)
git log --oneline -10
```

## File System Operations

### Disk usage and cleanup
```bash
# Check disk usage
df -h
du -sh * | sort -rh

# Find large files
find /path/to/search -type f -size +100M -exec ls -lh {} \;

# Clean old logs
find /var/log -name "*.log" -mtime +30 -delete
```

### Permission management
```bash
# Set executable permissions
chmod +x [SCRIPT-NAME]

# Change ownership
sudo chown [USER]:[GROUP] [FILE-OR-DIRECTORY]

# Recursive permission change
chmod -R 755 [DIRECTORY]
```

## Process Management

### Process monitoring
```bash
# View running processes
ps aux | grep [PROCESS-NAME]

# Interactive process viewer
htop

# Kill process by name
pkill [PROCESS-NAME]

# Kill process by PID
kill -9 [PID]
```

### Resource monitoring
```bash
# Memory usage
free -h

# CPU usage
top

# I/O statistics
iostat -x 1
```

## Emergency Recovery Commands

### Service restart sequence
```bash
# Standard service restart
sudo systemctl stop [SERVICE-NAME]
sudo systemctl start [SERVICE-NAME]
sudo systemctl status [SERVICE-NAME]

# Force kill if unresponsive
sudo pkill -f [SERVICE-NAME]
sudo systemctl start [SERVICE-NAME]
```

### Log investigation
```bash
# Check system logs for errors
journalctl -p err --since "1 hour ago"

# Monitor logs in real-time
tail -f /var/log/[LOG-FILE]

# Search for specific error patterns
grep -r "ERROR\|FATAL\|CRITICAL" /var/log/
```

## Configuration Validation

### Kubernetes configuration
```bash
# Validate YAML syntax
kubectl apply --dry-run=client -f [CONFIG-FILE]

# Check cluster connectivity
kubectl cluster-info

# Verify context
kubectl config current-context
```

### Docker configuration
```bash
# Validate Dockerfile
docker build --no-cache -t [IMAGE-NAME] .

# Check container health
docker inspect [CONTAINER-NAME] --format='{{.State.Health.Status}}'
```

### Base64 Line Wrap

Many systems expect base64 as a continuous string without line breaks, especially when used programmatically rather than for human reading.

-w0: Sets wrap width to 0, meaning no line breaks at all - the entire base64 output appears as one continuous string

```base
# Without -w0 (wrapped at 76 chars):
echo "hello world" | base64
aGVsbG8gd29ybGQK

# With -w0 (single line):
echo "hello world" | base64 -w0
aGVsbG8gd29ybGQK
```

### Setting a default remote for git 

When you have two remotes and you want to set one as the default for push/pull operations so that you can omit the remote name in commands like `git push` or `git pull`, you can set the default remote using the following command:

```
git branch --set-upstream-to=origin/main main
```
Where `origin` is listed alongside another "remote" source like `upstream` (for example) when you run `git remote -v`.

```bash

## Notes

- Replace all placeholder values (shown in brackets) with actual values appropriate for your environment
- Always verify commands in a test environment before running in production
- Use `--dry-run` flags where available to preview changes
- Keep backups before making significant configuration changes
- Monitor logs after executing commands to verify successful completion

## Quick Troubleshooting Workflow

1. **Identify the problem**: Check logs and service status
2. **Isolate the component**: Use diagnostic commands to narrow scope
3. **Apply fix**: Execute appropriate commands from above
4. **Verify resolution**: Confirm service is working properly
5. **Document**: Record what worked for future reference