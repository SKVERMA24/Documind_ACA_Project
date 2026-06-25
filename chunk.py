from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_text(text: str, chunk_size: int = 50, chunk_overlap: int = 10) -> list[str]:
    """
    Splits the input text into chunks using LangChain's RecursiveCharacterTextSplitter.
    
    Args:
        text (str): The raw input text.
        chunk_size (int): The maximum character length of each chunk.
        chunk_overlap (int): The overlapping character length between adjacent chunks.
        
    Returns:
        list[str]: A list of text chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return splitter.split_text(text)
