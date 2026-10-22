<#import "template.ftl" as layout>
<#assign forumHomeUrl = properties.forumHomeUrl!"http://localhost:3080/#/">
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <#if messageHeader??>
        ${messageHeader}
        <#else>
        ${message.summary}
        </#if>
    <#elseif section = "form">
    <div id="kc-info-message">
        <p class="instruction">${message.summary}<#if requiredActions??><#list requiredActions>: <b><#items as reqActionItem>${msg("requiredAction.${reqActionItem}")}<#sep>, </#items></b></#list><#else></#if></p>
        <#if skipLink??>
        <#else>
            <#if actionUri?has_content>
                <p><a href="${actionUri}">${kcSanitize(msg("proceedWithAction"))?no_esc}</a></p>
            <#else>
                <p><a id="backToApplication" href="${forumHomeUrl}">${kcSanitize(msg("backToApplication"))?no_esc}</a></p>
            </#if>
        </#if>
    </div>
    </#if>
</@layout.registrationLayout>
