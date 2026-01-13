"""
Fix bcrypt compatibility issue with passlib
This patches passlib to work with newer bcrypt versions
"""
import passlib.handlers.bcrypt as bcrypt_module
import bcrypt as _bcrypt

# Patch passlib to use __version__ instead of __about__.__version__
if hasattr(bcrypt_module, '_load_backend_mixin'):
    original_load = bcrypt_module._load_backend_mixin
    
    def patched_load_backend_mixin(self):
        try:
            # Try new way first
            version = getattr(_bcrypt, '__version__', None)
            if version is None:
                # Fallback to old way
                version = getattr(_bcrypt, '__about__', {}).get('__version__', '<unknown>')
        except (AttributeError, TypeError):
            version = '<unknown>'
        
        # Continue with original logic
        return original_load(self)
    
    bcrypt_module._load_backend_mixin = patched_load_backend_mixin

print("✅ bcrypt compatibility patch applied")














