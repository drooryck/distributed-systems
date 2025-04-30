// Lowkey not needed

import React, { createContext, useState, useEffect, useContext } from 'react';

const BACKGROUND_IMAGES = [
    '/backgrounds/deep-tetris-color.jpg',
    '/backgrounds/tetris-1920-x-1080-background-hyihqau5t3lalo4e.png',
    '/backgrounds/tetris-2560-x-1600-background-3bjbi7nyulqbller.jpg',
  ];

// Create the context
const BackgroundContext = createContext();

// Hook for components to access the background context
export function useBackground() {
  return useContext(BackgroundContext);
}

export function BackgroundProvider({ children }) {
  const [currentBgIndex, setCurrentBgIndex] = useState(0);
  const [backgroundImage, setBackgroundImage] = useState(null);
  
  // Function to preload and set a background image
  const loadBackgroundImage = (imagePath) => {
    const img = new Image();
    img.onload = () => {
      setBackgroundImage(img.src);
    };
    img.onerror = () => {
      console.error(`Failed to load background image: ${imagePath}`);
      setBackgroundImage(null);
    };
    img.src = imagePath;
  };
  
  // Function to manually change background
  const changeBackground = () => {
    const nextIndex = (currentBgIndex + 1) % BACKGROUND_IMAGES.length;
    setCurrentBgIndex(nextIndex);
    loadBackgroundImage(BACKGROUND_IMAGES[nextIndex]);
  };
  
  // Set up background image rotation on initial render
  useEffect(() => {
    // Load the first background image
    loadBackgroundImage(BACKGROUND_IMAGES[currentBgIndex]);
    
    // Set up a rotation interval (change every 30 seconds)
    const rotationInterval = setInterval(() => {
      changeBackground();
    }, 30000);
    
    // Clean up interval on unmount
    return () => clearInterval(rotationInterval);
  }, []); 
  
  // Value to be provided to consuming components
  const value = {
    backgroundImage,
    changeBackground,
    currentBgIndex
  };
  
  return (
    <BackgroundContext.Provider value={value}>
      {children}
    </BackgroundContext.Provider>
  );
}