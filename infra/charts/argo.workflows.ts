import { Chart, ChartProps, Duration, Helm } from 'cdk8s';
import { Secret } from 'cdk8s-plus-30';
import { Construct } from 'constructs';

import { ArgoDbName, ArgoDbUser, DefaultRegion } from '../constants.js';
import { applyDefaultLabels } from '../util/labels.js';

export interface ArgoWorkflowsProps {
  /**
   * Name of the temporary bucket used to store artifacts
   *
   * @example "linz-workflows-scratch"
   */
  tempBucketName: string;
  /**
   * Name of the Service Account used to run workflows
   *
   * @example "workflow-runner-sa"
   */
  saName: string;
  /**
   * Name of the EKS cluster
   *
   * @example "Workflows"
   */
  clusterName: string;
  /**
   * The Argo database endpoint
   *
   * @example "argodb-argodb4be14fa2-p8yjinijwbro.cmpyjhgv78aj.ap-southeast-2.rds.amazonaws.com"
   */
  argoDbEndpoint: string;
  /**
   * The Argo database password
   *
   * @example "eighoo5room0aeM^ahz0Otoh4aakiipo"
   */
  argoDbPassword: string;
}

/**
 * This is the version of the Helm chart for Argo Workflows https://github.com/argoproj/argo-helm/blob/25d7b519bc7fc37d2820721cd648f3a3403d0e38/charts/argo-workflows/Chart.yaml#L6
 *
 * (Do not mix up with Argo Workflows application version)
 */
const chartVersion = '0.41.0';

/**
 * This is the version of Argo Workflows for the `chartVersion` we're using
 * https://github.com/argoproj/argo-helm/blob/2730dc24c7ad69b98d3206705a5ebf5cb34dd96b/charts/argo-workflows/Chart.yaml#L2
 *
 */
const appVersion = 'v3.5.5';

export class ArgoWorkflows extends Chart {
  constructor(scope: Construct, id: string, props: ArgoWorkflowsProps & ChartProps) {
    super(scope, id, applyDefaultLabels(props, 'argo', appVersion, 'argo-workflows', 'workflows'));

    const artifactRepository = {
      archiveLogs: true,
      useStaticCredentials: false,
      s3: {
        accessKeySecret: { key: 'accesskey', name: '' },
        secretKeySecret: { key: 'secretkey', name: '' },
        bucket: props.tempBucketName,
        keyFormat:
          '{{workflow.creationTimestamp.Y}}-{{workflow.creationTimestamp.m}}/{{workflow.creationTimestamp.d}}-{{workflow.name}}/{{pod.name}}',
        region: DefaultRegion,
        endpoint: 's3.amazonaws.com',
        useSDKCreds: true,
        insecure: false,
      },
    };

    const argoDbSecret = new Secret(this, 'argo-postgres-config', {});
    argoDbSecret.addStringData('username', ArgoDbUser);
    argoDbSecret.addStringData('password', props.argoDbPassword);

    const persistence = {
      connectionPool: {
        maxIdleConns: 100,
        maxOpenConns: 0,
      },
      nodeStatusOffLoad: true,
      archive: true,
      archiveTTL: '', // never expire archived workflows
      postgresql: {
        host: props.argoDbEndpoint,
        port: 5432,
        database: ArgoDbName,
        tableName: 'argo_workflows',
        userNameSecret: { name: argoDbSecret.name, key: 'username' },
        passwordSecret: { name: argoDbSecret.name, key: 'password' },
        ssl: true,
        sslMode: 'require',
      },
    };

    const DefaultNodeSelector = {
      'eks.amazonaws.com/capacityType': 'ON_DEMAND',
      'kubernetes.io/arch': 'amd64',
    };

    new Helm(this, 'argo-workflows', {
      chart: 'argo-workflows',
      releaseName: 'argo-workflows',
      repo: 'https://argoproj.github.io/argo-helm',
      namespace: 'argo',
      version: chartVersion,
      values: {
        server: {
          replicas: 2,
          extraEnv: [
            /** Disable the "first time" popups that pop up every time  */
            { name: 'FIRST_TIME_USER_MODAL', value: 'false' },
            { name: 'FEEDBACK_MODAL', value: 'false' },
            { name: 'NEW_VERSION_MODAL', value: 'false' },
          ],
          nodeSelector: { ...DefaultNodeSelector },
          extraArgs: ['--auth-mode=server'],
        },
        artifactRepository,
        controller: {
          /* Tells Fluent Bit to not send Argo Controller log to CloudWatch
           *  https://github.com/argoproj/argo-workflows/issues/11657 is spamming the logs
           *  and increase our logs storage cost.
           */
          podAnnotations: { 'fluentbit.io/exclude': 'true' },
          nodeSelector: { ...DefaultNodeSelector },
          workflowNamespaces: ['argo'],
          extraArgs: [],
          // FIXME: workaround for https://github.com/argoproj/argo-workflows/issues/11657
          extraEnv: [{ name: 'WATCH_CONTROLLER_SEMAPHORE_CONFIGMAPS', value: 'false' }],
          persistence,
          replicas: 2,
          workflowDefaults: {
            spec: {
              serviceAccountName: props.saName,
              ttlStrategy: { secondsAfterCompletion: Duration.days(1).toSeconds() },
              podGC: { strategy: 'OnPodCompletion' },
              tolerations: [
                {
                  key: 'karpenter.sh/capacity-type',
                  operator: 'Equal',
                  value: 'spot',
                  effect: 'NoSchedule',
                },
              ],
              parallelism: 3,
              templateDefaults: {
                /** TODO: `nodeAntiAffinity` - to retry on different node - is not working yet (https://github.com/argoproj/argo-workflows/pull/12701)
                 * `affinity: { nodeAntiAffinity: {} }` seems to break `karpenter`, need more investigation
                 */
                retryStrategy: { limit: 2, retryPolicy: 'OnError' },
              },
            },
          },
        },
        workflow: {
          rbac: { create: true },
          serviceAccount: { create: false, name: props.saName },
        },
      },
    });
  }
}
