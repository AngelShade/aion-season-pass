import java.nio.file.*;
import java.security.*;
import java.security.spec.X509EncodedKeySpec;
import java.util.*;

class VerifySignatures {
    public static void main(String[] args) throws Exception {
        Path staged=Path.of(args[0]), root=Path.of(args[1]);
        var key=KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(HexFormat.of().parseHex(Files.readString(staged.resolve("Addon.key")).strip())));
        for(String rel:List.of("Plugin/RelicCalc/RelicCalc.pak","bin32/bin32.pak","Data/func_pet/func_pet.pak")) {
            Signature v=Signature.getInstance("SHA1withRSA"); v.initVerify(key);
            v.update(Files.readAllBytes(Files.exists(staged.resolve(rel))?staged.resolve(rel):root.resolve(rel)));
            if(!v.verify(HexFormat.of().parseHex(Files.readString(staged.resolve(rel+".sig")).strip()))) throw new SecurityException("Invalid signature: "+rel);
        }
        System.out.println("OK: all three staged addon signatures verified by Java RSA/SHA1.");
    }
}
