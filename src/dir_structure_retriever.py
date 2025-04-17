import os
import sys

def tree_command(directory='.', prefix='', is_last=False, max_level=None, level=0, exclude=None):
    """
    Return a string representation of the directory structure similar to the tree command.
    
    Args:
        directory (str): Directory to start from
        prefix (str): Prefix for the current item
        is_last (bool): If True, use the "└── " prefix, else "├── "
        max_level (int, optional): Maximum depth to traverse
        level (int): Current level in the tree
        exclude (list, optional): List of directories/files to exclude
        
    Returns:
        str: Formatted tree output
    """
    
    if exclude is None:
        exclude = []
    
    if max_level is not None and level > max_level:
        return ""
    
    output = []
    
    # Get items in the directory, excluding hidden files and excluded items
    try:
        items = [item for item in os.listdir(directory) 
                if not item.startswith('.') and item not in exclude]
    except PermissionError:
        return prefix + ("└── " if is_last else "├── ") + os.path.basename(directory) + " [Permission Denied]\n"
    except Exception as e:
        return prefix + ("└── " if is_last else "├── ") + os.path.basename(directory) + f" [Error: {str(e)}]\n"
    # Sort directories first, then files
    items.sort(key=lambda x: (not os.path.isdir(os.path.join(directory, x)), x))
    
    # Root directory
    if level == 0:
        output.append(directory)
    
    # Process each item
    for i, item in enumerate(items):
        item_path = os.path.join(directory, item)
        item_is_last = i == len(items) - 1
        
        # Use different connector styles based on whether this is the last item
        connector = "└── " if item_is_last else "├── "
        output.append(prefix + connector + item)
        
        # Recursively process directories
        if os.path.isdir(item_path):
            # Extend prefix for children:
            # - If this is the last item, add spaces for the next level
            # - If not, add a vertical line for the next level
            next_prefix = prefix + ("    " if item_is_last else "│   ")
            
            # Recursively process directory
            subtree = tree_command(
                item_path, 
                next_prefix, 
                False, 
                max_level, 
                level + 1, 
                exclude
            )
            
            if subtree:
                output.append(subtree)
    
    return "\n".join(output)

def main():
    directory = '.'
    max_level = None
    exclude = []
    
    # Parse command line arguments
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '-L' and i + 1 < len(args):
            try:
                max_level = int(args[i + 1])
                i += 2
            except ValueError:
                i += 1
        elif args[i] == '-I' and i + 1 < len(args):
            exclude.extend(args[i + 1].split(','))
            i += 2
        elif not args[i].startswith('-') and os.path.isdir(args[i]):
            directory = args[i]
            i += 1
        else:
            i += 1
    
    print(tree_command(directory, max_level=max_level, exclude=exclude))

if __name__ == "__main__":
    main()
