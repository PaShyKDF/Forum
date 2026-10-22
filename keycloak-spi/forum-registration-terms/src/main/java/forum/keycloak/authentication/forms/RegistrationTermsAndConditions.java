package forum.keycloak.authentication.forms;

import java.util.Collections;
import java.util.List;
import javax.ws.rs.core.MultivaluedMap;
import org.keycloak.Config;
import org.keycloak.authentication.FormAction;
import org.keycloak.authentication.FormActionFactory;
import org.keycloak.authentication.FormContext;
import org.keycloak.authentication.ValidationContext;
import org.keycloak.events.Errors;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.AuthenticationExecutionModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.models.utils.FormMessage;
import org.keycloak.provider.ConfiguredProvider;
import org.keycloak.provider.ProviderConfigProperty;


/**
 * FormAction: без галочки согласия регистрация отклоняется на сервере.
 *
 * Ожидает поле формы {@code termsAccepted}.
 * В шаблон передаёт {@code termsAcceptanceRequired=true}.
 */
public class RegistrationTermsAndConditions
        implements FormAction, FormActionFactory, ConfiguredProvider {

    public static final String PROVIDER_ID =
            "registration-terms-and-conditions";

    protected static final String FIELD = "termsAccepted";

    private static final AuthenticationExecutionModel.Requirement[]
            REQUIREMENT_CHOICES = {
                AuthenticationExecutionModel.Requirement.REQUIRED,
                AuthenticationExecutionModel.Requirement.DISABLED,
            };

    @Override
    public String getDisplayType() {
        return "Terms and conditions";
    }

    @Override
    public String getReferenceCategory() {
        return "terms-and-conditions";
    }

    @Override
    public boolean isConfigurable() {
        return false;
    }

    @Override
    public AuthenticationExecutionModel.Requirement[]
            getRequirementChoices() {
        return REQUIREMENT_CHOICES;
    }

    @Override
    public boolean isUserSetupAllowed() {
        return false;
    }

    @Override
    public void buildPage(
            FormContext context,
            LoginFormsProvider form
    ) {
        form.setAttribute(
                "termsAcceptanceRequired",
                Boolean.TRUE
        );
    }

    @Override
    public void validate(ValidationContext context) {
        MultivaluedMap<String, String> formData =
                context.getHttpRequest().getDecodedFormParameters();
        if (formData.containsKey(FIELD)) {
            context.success();
            return;
        }
        context.error(Errors.INVALID_REGISTRATION);
        context.validationError(
                formData,
                Collections.singletonList(
                        new FormMessage(
                                FIELD,
                                "termsAcceptanceRequired"
                        )
                )
        );
    }

    @Override
    public void success(FormContext context) {
        // no-op
    }

    @Override
    public boolean requiresUser() {
        return false;
    }

    @Override
    public boolean configuredFor(
            KeycloakSession session,
            RealmModel realm,
            UserModel user
    ) {
        return true;
    }

    @Override
    public void setRequiredActions(
            KeycloakSession session,
            RealmModel realm,
            UserModel user
    ) {
        // no-op
    }

    @Override
    public String getHelpText() {
        return "Requires accepting forum rules on registration.";
    }

    @Override
    public List<ProviderConfigProperty> getConfigProperties() {
        return Collections.emptyList();
    }

    @Override
    public FormAction create(KeycloakSession session) {
        return this;
    }

    @Override
    public void init(Config.Scope config) {
        // no-op
    }

    @Override
    public void postInit(KeycloakSessionFactory factory) {
        // no-op
    }

    @Override
    public void close() {
        // no-op
    }

    @Override
    public String getId() {
        return PROVIDER_ID;
    }
}
